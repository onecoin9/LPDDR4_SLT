using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Net.Sockets;
using System.Net;
using Hsg.Common;
using System.Threading;
namespace Hsg.BLL.Net
{
    public delegate bool IUdpRecvDataHandle(byte[] data, IPEndPoint ipEndPoint);
    public class UdpServer
    {
        /// <summary>
        /// 接收 sock
        /// </summary>
        private UdpClient _server;

        private IUdpRecvDataHandle _recvDataHandle;
        private bool _isRun;
        private static CancellationTokenSource _cts;
        private string LOG_TAG = "UDP_CONN";
        public UdpServer(IUdpRecvDataHandle dataHandle)
        {
            _isRun = false;
            _recvDataHandle = dataHandle;
        }
        private bool StartInternal(Action initAction)
        {
            if (_isRun) return false;
            try
            {
                initAction.Invoke();
                if(_server == null)
                {
                    return false;
                }
                _isRun = true;
                _cts = new CancellationTokenSource();
                // 使用 Task.Run 启动异步接收循环
                Task.Run(() => RecvTaskAsync(_cts.Token), _cts.Token)
                   .ContinueWith(t =>
                   {
                       if (t.IsFaulted)
                       {
                           Hlog.E(LOG_TAG, $"RecvTaskAsync failed: {t.Exception?.Flatten().Message}");
                           Stop(); // 发生异常时自动停止
                       }
                   });

                Hlog.I(LOG_TAG, $"UDP server started on port {_server.Client.LocalEndPoint}");
                return true;
            }
            catch (SocketException ex) when (ex.SocketErrorCode == SocketError.AddressAlreadyInUse)
            {
                Hlog.E(LOG_TAG, $"udp port is already in use: {ex.Message}");
            }
            catch (Exception ex)
            {
                Hlog.E(LOG_TAG, $"Failed to start UDP server: {ex.Message}");
                Stop(); // 清理资源
            }

            return false;
        }
        public bool Start(int recvPort)
        {
            return StartInternal(() => { _server = new UdpClient(recvPort); });
        }



        public bool Start()
        {
            return StartInternal(() =>
            {
                _server = new UdpClient();
                _server.Client.Bind(new IPEndPoint(IPAddress.Any, 0));
            });
        }


        public void Stop()
        {
            if (_isRun)
            {
                _isRun = false;
                try
                {
                    _cts.Cancel();
                    _server.Close();
                    //_client.Close();
                    
                    //_client = null;
                }
                catch
                {

                }finally
                {
                    _server = null;
                }
            }

        }

        private async Task RecvTaskAsync(CancellationToken token)
        {
            while (!token.IsCancellationRequested && _server != null)
            {
                try
                {
                    var result = await _server.ReceiveAsync();
                    RecvDataHandle(result.Buffer, result.RemoteEndPoint);
                }
                catch (OperationCanceledException) { break; }
                catch (Exception ex) { Hlog.E(LOG_TAG, $"Recv error: {ex.Message}"); }
            }
        }

        public int SendData(byte[] data, IPEndPoint ipEndPoint)
        {
            int ret = 0;
            if (_isRun)
            {
                try
                {
                    ret = _server.Send(data, data.Length, ipEndPoint);
                }
                catch (Exception ex)
                {
                    ret = -1;
                    Hlog.E(LOG_TAG, "Send error:" + ex.Message);
                }
            }
            return ret;
        }
        public int SendData(byte[] data, int datalen, IPEndPoint ipEndPoint)
        {
            int ret = 0;
            if (_isRun)
            {
                try
                {
                    ret = _server.Send(data, datalen, ipEndPoint);
                }
                catch (Exception ex)
                {
                    ret = -1;
                    Hlog.E(LOG_TAG, "Send error:" + ex.Message);
                }
            }
            return ret;
        }
        private bool RecvDataHandle(byte[] data, IPEndPoint ipEndPoint)
        {
            if (_recvDataHandle != null && data != null && data.Length > 0)
            {
                return _recvDataHandle(data, ipEndPoint);
            }
            return true;
        }
    }


}
