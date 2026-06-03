using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Net.Sockets;
using System.Net;
using TBM01.Common;
using System.Threading;
namespace TBM01.BLL.Net
{

    public class UdpConfig
    {
        private IOnMemberChange onValueChange;
        public UdpConfig(IOnMemberChange onMemberChange)
        {
            this.onValueChange = onMemberChange;
        }
        private int _recvPort;
        public int recvPort
        {
            get
            {
                return _recvPort;
            }

        }
        /// <summary>
        /// 发送的IP
        /// </summary>
        private IPAddress _sendIP;
        public IPAddress sendIP
        {
            get { return _sendIP; }

        }
        /// <summary>
        /// 发送的目标端口
        /// </summary>
        private int _sendPort;
        public int sendPort
        {
            get
            {
                return _sendPort;
            }

        }
        public void SetValue(IPAddress destIP, int recvPort, int sendPort)
        {
            bool changeFlag = false;
            if (_recvPort != recvPort)
            {
                _recvPort = recvPort;
                changeFlag = true;
            }

            if (_sendPort != sendPort)
            {
                _sendPort = sendPort;
                changeFlag = true;
            }

            if (_sendIP != destIP)
            {
                _sendIP = destIP;
                changeFlag = true;
            }

            if (changeFlag)
            {
                if (onValueChange != null)
                {
                    onValueChange();
                }
            }
        }
    }
    public class UdpConn
    {
        /// <summary>
        /// 接收 sock
        /// </summary>
        private UdpClient _server;
        /// <summary>
        /// 发送 sock
        /// </summary>
        private UdpClient _client;
        private IPEndPoint _ipRecvPoint;
        private IPEndPoint _ipSendPoint;
        private IRecvDataHandle _recvDataHandle;
        private bool _isRun;
        public UdpConn(IRecvDataHandle dataHandle)
        {
            //_server = new UdpClient();
            //_client = new UdpClient();
            _isRun = false;
            _recvDataHandle = dataHandle;
        }

        public bool start(UdpConfig config)
        {
            if (_isRun)
            {
                return false;
            }

            try
            {
                _server = new UdpClient(Convert.ToInt16(config.recvPort));
                _client = new UdpClient();
                _ipRecvPoint = new IPEndPoint(IPAddress.Any, 0);
                _ipSendPoint = new IPEndPoint(config.sendIP, config.sendPort);

                ThreadPool.QueueUserWorkItem(new WaitCallback(RecvTask), null);
                _isRun = true;
                return true;
            }
            catch (Exception ex)
            {
                Hlog.E(ex.Message);
            }
            return false;
        }
        public void stop()
        {
            if (_isRun)
            {
                _isRun = false;
                try
                {
                    _server.Close();
                    _client.Close();
                    _server = null;
                    _client = null;
                }
                catch
                {

                }
            }

        }
        private void RecvTask(object param)
        {
            while (_isRun)
            {
                try
                {
                    byte[] recvData = _server.Receive(ref _ipRecvPoint);
                    RecvDataHandle(recvData);
                }
                catch (Exception ex)
                {
                    //Hlog.E("Recv error:" + ex.Message);
                    break;
                }
            }
        }
        public int SendData(byte[] data)
        {
            int ret = 0;
            if (_isRun)
            {
                try
                {
                    ret = _client.Send(data, data.Length, _ipSendPoint);
                }
                catch (Exception ex)
                {
                    ret = -1;
                    Hlog.E("Send error:" + ex.Message);
                }
            }
            return ret;
        }
        private bool RecvDataHandle(byte[] data)
        {
            if (_recvDataHandle != null)
            {
                return _recvDataHandle(data);
            }
            return true;
        }
    }


}
