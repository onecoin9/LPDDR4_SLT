using Hsg.Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Hsg.BLL.Net
{
    //public delegate bool IUdpRecvDataHandle(byte[] data, IPEndPoint ipEndPoint);
    public class UdpReceiver
    {
        private UdpClient _server;
        private IUdpRecvDataHandle _recvDataHandle;
        private bool _isRun;
        public UdpReceiver(IUdpRecvDataHandle dataHandle)
        {
            _isRun = false;
            _recvDataHandle = dataHandle;
        }
        public bool start(int rxPort)
        {
            if (_isRun)
            {
                return false;
            }
            try
            {
                _server = new UdpClient(rxPort);
                //_server.Client.ReceiveTimeout = 1000;
                _isRun = true;
                ThreadPool.QueueUserWorkItem(new WaitCallback(RecvTask), null);
                return true;
            }
            catch (Exception ex)
            {
                //Hlog.E(ex.Message);
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
                   // _server.Client.Shutdown(SocketShutdown.Both);
                    _server.Close();
                    _server = null;
                }
                catch (Exception ex)
                {
                    // Hlog.E("close" + ex.Message);
                }
            }


        }
        private void RecvTask(object param)
        {
            while (_isRun)
            {
                try
                {
                    IPEndPoint recvPoint = new IPEndPoint(IPAddress.Any, 0);
                    byte[] recvData = _server.Receive(ref recvPoint);
                    if (recvData != null || recvData.Length > 0)
                    {
                        RecvDataHandle(recvData, recvPoint);
                    }

                }
                catch (Exception ex)
                {
                    //Hlog.E("Recv error:" + ex.Message);
                    continue;
                }
            }

        }
        private bool RecvDataHandle(byte[] data, IPEndPoint ipEndPoint)
        {
            Hlog.I("Recv data from" + ipEndPoint.ToString());
            if (_recvDataHandle != null)
            {
                return _recvDataHandle(data, ipEndPoint);
            }
            return true;
        }
    }
}
