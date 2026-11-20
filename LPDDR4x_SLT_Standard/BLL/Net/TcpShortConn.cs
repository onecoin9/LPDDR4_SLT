using System;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;
using Hsg.Common;

namespace Hsg.BLL.Net
{
    /// <summary>
    /// TCP 短连接服务端：每次 Accept → Read → 回调处理 → Write response → Close
    /// </summary>
    public class TcpShortServer
    {
        private TcpListener _listener;
        private volatile bool _running;
        private CancellationTokenSource _cts;
        private Func<byte[], byte[]> _onRequest;
        private Action<string> _onClientConnected;

        public bool IsRunning => _running;

        public void Start(ushort port, Func<byte[], byte[]> onRequest, Action<string> onClientConnected = null)
        {
            if (_running) return;
            _onRequest = onRequest;
            _onClientConnected = onClientConnected;
            _running = true;
            _cts = new CancellationTokenSource();
            Task.Run(() => AcceptLoop(port, _cts.Token));
        }

        public void Stop()
        {
            _running = false;
            try { _cts?.Cancel(); } catch { }
            try { _listener?.Stop(); } catch { }
            _listener = null;
        }

        private async Task AcceptLoop(ushort port, CancellationToken ct)
        {
            try
            {
                _listener = new TcpListener(IPAddress.Any, port);
                _listener.Start();
                Hlog.I("TcpShortServer", $"listening on port {port}");
            }
            catch (Exception ex)
            {
                Hlog.E("TcpShortServer", $"start listener failed: {ex.Message}");
                _running = false;
                return;
            }

            while (_running && !ct.IsCancellationRequested)
            {
                TcpClient client = null;
                try
                {
                    var acceptTask = _listener.AcceptTcpClientAsync();
                    if (await Task.WhenAny(acceptTask, Task.Delay(1000, ct)) != acceptTask)
                        continue;
                    client = acceptTask.Result;
                }
                catch { continue; }

                // 每个连接在独立 task 中处理，支持并发（fire-and-forget）
                var captured = client;
                _ = Task.Run(() => HandleClient(captured));
            }

            try { _listener?.Stop(); } catch { }
        }

        private void HandleClient(TcpClient client)
        {
            try
            {
                using (client)
                {
                    client.ReceiveTimeout = 5000;
                    client.SendTimeout = 3000;

                    // 记录客户端 IP
                    try
                    {
                        var ep = client.Client?.RemoteEndPoint as IPEndPoint;
                        if (ep != null)
                            _onClientConnected?.Invoke(ep.Address.ToString());
                    }
                    catch { }

                    NetworkStream stream = client.GetStream();

                    // 读取全部请求数据
                    byte[] buffer = new byte[4096];
                    int totalRead = 0;
                    while (totalRead < buffer.Length)
                    {
                        int read = stream.Read(buffer, totalRead, buffer.Length - totalRead);
                        if (read <= 0) break;
                        totalRead += read;
                        // 简单判定：收到完整 JSON 就停止读取
                        string soFar = System.Text.Encoding.UTF8.GetString(buffer, 0, totalRead);
                        if (soFar.TrimEnd().EndsWith("}"))
                            break;
                    }

                    if (totalRead > 0)
                    {
                        byte[] requestData = new byte[totalRead];
                        Array.Copy(buffer, requestData, totalRead);

                        byte[] response = _onRequest?.Invoke(requestData);
                        if (response != null && response.Length > 0)
                        {
                            stream.Write(response, 0, response.Length);
                            stream.Flush();
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Hlog.D("TcpShortServer", $"handle client error: {ex.Message}");
            }
        }
    }

    /// <summary>
    /// TCP 短连接客户端：Connect → Write → Read response → Close
    /// </summary>
    public static class TcpShortClient
    {
        public static byte[] Send(string ip, ushort port, byte[] data, int timeoutMs = 5000)
        {
            try
            {
                using (var client = new TcpClient())
                {
                    client.ReceiveTimeout = timeoutMs;
                    client.SendTimeout = 3000;

                    var ar = client.BeginConnect(ip, (int)port, null, null);
                    if (!ar.AsyncWaitHandle.WaitOne(3000, true))
                    {
                        client.Close();
                        Hlog.E("TcpShortClient", $"connect timeout: {ip}:{port}");
                        return null;
                    }
                    client.EndConnect(ar);

                    NetworkStream stream = client.GetStream();
                    stream.Write(data, 0, data.Length);
                    stream.Flush();

                    byte[] buffer = new byte[4096];
                    int totalRead = 0;
                    while (totalRead < buffer.Length)
                    {
                        int read = stream.Read(buffer, totalRead, buffer.Length - totalRead);
                        if (read <= 0) break;
                        totalRead += read;
                        string soFar = System.Text.Encoding.UTF8.GetString(buffer, 0, totalRead);
                        if (soFar.TrimEnd().EndsWith("}"))
                            break;
                    }

                    if (totalRead > 0)
                    {
                        byte[] response = new byte[totalRead];
                        Array.Copy(buffer, response, totalRead);
                        return response;
                    }
                }
            }
            catch (Exception ex)
            {
                Hlog.E("TcpShortClient", $"send error: {ex.Message}");
            }
            return null;
        }
    }
}
