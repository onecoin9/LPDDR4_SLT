using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Net.Sockets;
using System.Net;
using System.Threading;
using Hsg.Common;
using System.Net.Http;

namespace Hsg.BLL.Net
{
    public enum TcpConnMode
    {
        Client = 0,
        Server = 1,
    }

    public class TcpClientConn
    {
        private TcpClient _tcpClient;
        private TcpListener _tcpListener;
        private NetworkStream _recvStream;
        private Action<bool> _stateDetect;
        private IRecvDataHandle _recvDataHandle;
        private bool _connRun; // 运行一次，关联一个处理线程，下次只关闭连接，不销毁线程
        private bool _connectReady;
        private bool _connEnable;// true 就保持连接 false 就关闭
        private readonly object _writeLock = new object();
        private string MOD_ID = "TcpClient:";
        // private TcpClientConfig _config;
        private string _destIp;
        private ushort[] _destPorts;
        private int _retryCount;
        private bool _retryConn;// 重新连接
        private string _listenIp;
        private ushort _listenPort;
        private TcpConnMode _mode;
        public bool IsConnected
        {
            get { return _connectReady; }
        }
        public bool TryGetRemoteEndpoint(out string remoteIp, out ushort remotePort)
        {
            remoteIp = string.Empty;
            remotePort = 0;
            try
            {
                IPEndPoint endPoint = _tcpClient?.Client?.RemoteEndPoint as IPEndPoint;
                if (endPoint == null)
                {
                    return false;
                }
                remoteIp = endPoint.Address.ToString();
                remotePort = (ushort)endPoint.Port;
                return true;
            }
            catch
            {
                return false;
            }
        }
        public TcpClientConn(IRecvDataHandle recvDataHandle, Action<bool> stateNotify)
        {
            _recvDataHandle = recvDataHandle;
            _stateDetect = stateNotify;
            _connRun = false;
            _connectReady = false;
            _connEnable = false;
            _retryConn = false;
            _retryCount = 0;
            _mode = TcpConnMode.Client;
            _listenIp = "0.0.0.0";
            _listenPort = 0;
        }
        private void OnStateChange(bool isConn)
        {
            if (_stateDetect != null)
            {
                _stateDetect(isConn);
            }
        }
        public bool OpenConn(string despIp, ushort destPort)
        {
            IPAddress addr;
            _mode = TcpConnMode.Client;
            _destIp = despIp;
            _destPorts = new ushort[1];
            _destPorts[0] = destPort;
            MOD_ID += despIp;
            if (_destIp.Length <= 0 || !IPAddress.TryParse(_destIp, out addr))
            {
                return false;
            }
            if (_connRun)
            {
                _connEnable = true;
                return true;
            }
            _connRun = true;
            _connEnable = true;
            // _tcpClient = new TcpClient(config.DestIp,int.Parse(config.DestPort));
            //ThreadPool.QueueUserWorkItem(new WaitCallback(ClientRecvWorker));
            Task.Run(async () => await ClientRecvWorker());
            return true;
        }

        public bool OpenConn(string despIp, ushort[] destPorts)
        {
            IPAddress addr;
            _mode = TcpConnMode.Client;
            if (destPorts.Length == 0)
            {
                return false;
            }
            _destIp = despIp;
            MOD_ID += despIp;
            _destPorts = new ushort[destPorts.Length];
            Array.Copy(destPorts, _destPorts, destPorts.Length);

            if (_destIp.Length <= 0 || !IPAddress.TryParse(_destIp, out addr))
            {
                return false;
            }
            if (_connRun)
            {
                _connEnable = true;
                return true;
            }
            _connRun = true;
            _connEnable = true;
            // _tcpClient = new TcpClient(config.DestIp,int.Parse(config.DestPort));
            //ThreadPool.QueueUserWorkItem(new WaitCallback(ClientRecvWorker));
            Task.Run(async () => await ClientRecvWorker());
            return true;
        }

        public bool OpenServer(string listenIp, ushort listenPort)
        {
            IPAddress addr;
            _mode = TcpConnMode.Server;
            _listenPort = listenPort;
            _listenIp = string.IsNullOrWhiteSpace(listenIp) ? "0.0.0.0" : listenIp;
            if (!IPAddress.TryParse(_listenIp, out addr))
            {
                return false;
            }
            if (_listenPort == 0)
            {
                return false;
            }
            MOD_ID = "TcpServer:" + _listenIp + ":" + _listenPort;
            if (_connRun)
            {
                _connEnable = true;
                return true;
            }
            _connRun = true;
            _connEnable = true;
            Task.Run(async () => await ServerRecvWorker(addr));
            return true;
        }

        public void CloseConn()
        {
            if (_connRun)
            {
                _connEnable = false;
            }
        }
        public bool SendData(byte[] data, int dataLen)
        {
            bool ret = false;
            if (_connectReady && dataLen > 0 && _tcpClient != null)
            {
                try
                {
                    NetworkStream wStream = _tcpClient.GetStream();
                    lock (_writeLock)
                    {
                        wStream.Write(data, 0, dataLen);
                        wStream.Flush();
                    }
                    ret = true;
                }
                catch (Exception ex)
                {
                    Hlog.E(MOD_ID, $"SendData failed: {ex.Message}");
                    _retryConn = true;
                }
            }
            else
            {
                Hlog.W(MOD_ID, $"SendData precondition fail: ready={_connectReady} len={dataLen} client={_tcpClient != null}");
            }
            return ret;
        }
        private async Task ClientRecvWorker()
        {
            byte[] dataBuf = new byte[256];
            bool last_state = false;
            ushort retryCount = 0;
            int portCount = _destPorts.Length;
            //NetworkStream recvStream = null;
            while (true)
            {
                if (!_connEnable)
                {
                    if (_connectReady)
                    {
                        Hlog.D(MOD_ID, "!_connEnable");
                        _retryConn = false;
                        ReleaseConn();
                    }
                    await Task.Delay(1000);
                    continue;
                }
                else if (!_connectReady)
                {
                    int portIndex = retryCount % portCount;
                    retryCount++;
                    Hlog.D(MOD_ID, "conn port:" + _destPorts[portIndex]);
                    try
                    {
                        //_tcpClient = new TcpClient(_destIp, _destPorts[portIndex]);
                        TcpClient tcpClient = new TcpClient();
                        IAsyncResult asyncResult = tcpClient.BeginConnect(_destIp, _destPorts[portIndex], null, null);
                        // 等待连接完成或超时
                        int waitMilliSecond = 2000;
                        if (_retryCount >= 3)
                        {
                            waitMilliSecond = 5000;
                        }
                        if (!asyncResult.AsyncWaitHandle.WaitOne(waitMilliSecond, true))
                        {
                            tcpClient.Close();
                            throw new TimeoutException("连接超时");
                        }

                        tcpClient.EndConnect(asyncResult);
                        _tcpClient = tcpClient;
                        //_tcpClient = new TcpClient();
                        // await _tcpClient.ConnectAsync(_config.DestIp, int.Parse(_config.DestPort));
                        Socket socket = _tcpClient.Client;
                        socket.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.KeepAlive, true);
                        byte[] inValues = new byte[12];
                        BitConverter.GetBytes((uint)1).CopyTo(inValues, 0); // onoff  
                        BitConverter.GetBytes((uint)(30 * 1000)).CopyTo(inValues, 4); // time  
                        BitConverter.GetBytes((uint)(3 * 1000)).CopyTo(inValues, 8); // interval  
                        socket.IOControl(IOControlCode.KeepAliveValues, inValues, null);
                        last_state = _tcpClient.Connected;
                        _recvStream = _tcpClient.GetStream();
                        _connectReady = true;
                        OnStateChange(true);
                        Hlog.E(MOD_ID, $"connected");
                        // Console.WriteLine("connected.");
                    }
                    catch (Exception ex)
                    {
                        Hlog.E(MOD_ID, $"connect timeout: {ex.Message}");
                        await Task.Delay(1000);
                        _retryCount++;
                        if (_retryCount > 3)
                        {
                            _retryCount = 3;
                        }
                        continue;
                    }
                }

                if (_tcpClient.Connected)
                {
                    _retryCount = 0;
                    while (_connEnable && _connectReady && _tcpClient.Connected)
                    {
                        Byte[] readData = null;
                        int len = 0;
                        try
                        {
                            if (_tcpClient.Client.Poll(500 * 1000, SelectMode.SelectRead))
                            {
                                if (_recvStream.DataAvailable)
                                {
                                    len = await _recvStream.ReadAsync(dataBuf, 0, 256);
                                    if (len > 0)
                                    {
                                        readData = new byte[len];
                                        Array.Copy(dataBuf, readData, len);
                                    }
                                    else
                                    {
                                        Hlog.D(MOD_ID, "recv not available");
                                        _retryConn = true;
                                        break;
                                    }
                                }
                                else //if(!_tcpClient.Client.Connected)
                                {
                                    Hlog.D(MOD_ID, "socket disconnect");
                                    _retryConn = true;
                                    break;
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            Hlog.E(MOD_ID, ex.Message);
                            _retryConn = true;
                            break;
                        }
                        // 分开 处理避免异常断开
                        if (len > 0)
                        {
                            try
                            {
                                OnRecvDataHandle(readData);
                            }
                            catch (Exception ex)
                            {
                                Hlog.E(MOD_ID, ex.Message);
                                break;
                            }
                        }
                    }
                    if (!_tcpClient.Connected)
                    {
                        Hlog.D(MOD_ID, "conn break");
                        _retryConn = true;
                    }
                    //  
                }
                else
                {
                    Hlog.D(MOD_ID, "conn not Connected");
                    _retryConn = true;
                }
                if (_retryConn)
                {
                    _retryConn = false;
                    ReleaseConn();
                }

                //Thread.Sleep(50);
                await Task.Delay(100);
            }
        }

        private async Task ServerRecvWorker(IPAddress listenAddr)
        {
            byte[] dataBuf = new byte[256];
            while (true)
            {
                if (!_connEnable)
                {
                    if (_connectReady)
                    {
                        _retryConn = false;
                        ReleaseConn();
                    }
                    StopListener();
                    await Task.Delay(1000);
                    continue;
                }

                if (!_connectReady)
                {
                    try
                    {
                        if (_tcpListener == null)
                        {
                            _tcpListener = new TcpListener(listenAddr, _listenPort);
                            _tcpListener.Start();
                            Hlog.I(MOD_ID, "listen start");
                        }

                        Hlog.I(MOD_ID, "waiting client...");
                        _tcpClient = await _tcpListener.AcceptTcpClientAsync();
                        _recvStream = _tcpClient.GetStream();
                        _connectReady = true;
                        OnStateChange(true);
                        Hlog.I(MOD_ID, "client connected");
                    }
                    catch (Exception ex)
                    {
                        Hlog.E(MOD_ID, "listen/accept fail:" + ex.Message);
                        // Ensure a failed listener is fully reset so next loop can recreate and restart listening.
                        StopListener();
                        await Task.Delay(1000);
                        continue;
                    }
                }

                while (_connEnable && _connectReady && _tcpClient != null && _tcpClient.Connected)
                {
                    int len = 0;
                    byte[] readData = null;
                    try
                    {
                        if (_tcpClient.Client.Poll(500 * 1000, SelectMode.SelectRead))
                        {
                            if (_recvStream.DataAvailable)
                            {
                                len = await _recvStream.ReadAsync(dataBuf, 0, dataBuf.Length);
                                if (len > 0)
                                {
                                    readData = new byte[len];
                                    Array.Copy(dataBuf, readData, len);
                                }
                                else
                                {
                                    _retryConn = true;
                                    break;
                                }
                            }
                            else
                            {
                                _retryConn = true;
                                break;
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        Hlog.E(MOD_ID, ex.Message);
                        _retryConn = true;
                        break;
                    }

                    if (len > 0 && readData != null)
                    {
                        try
                        {
                            OnRecvDataHandle(readData);
                        }
                        catch (Exception ex)
                        {
                            Hlog.E(MOD_ID, ex.Message);
                            _retryConn = true;
                            break;
                        }
                    }
                }

                if (_retryConn)
                {
                    _retryConn = false;
                    ReleaseConn();
                }
                await Task.Delay(100);
            }
        }

        private void ReleaseConn()
        {
            Hlog.D(MOD_ID, "ReleaseConn");
            try
            {
                // Console.WriteLine("ReleaseConn.");
                _connectReady = false;
                OnStateChange(false);
                _tcpClient?.Close();
                _recvStream?.Close();
                _tcpClient = null;
                _recvStream = null;
                if (_mode == TcpConnMode.Server)
                {
                    StopListener();
                }
            }
            catch (Exception ex)
            {
                Hlog.E(ex.Message);
            }

        }

        private void StopListener()
        {
            try
            {
                _tcpListener?.Stop();
                _tcpListener = null;
            }
            catch (Exception ex)
            {
                Hlog.E(MOD_ID, "stop listener fail:" + ex.Message);
            }
        }

        private void OnRecvDataHandle(byte[] data)
        {
            if (_recvDataHandle != null)
            {
                _recvDataHandle(data);
            }
        }
    }
}
