using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading.Tasks;
using Hsg.BLL.config;
using Hsg.BLL.Net;
using Hsg.Common;

namespace Hsg.BLL
{
    //public delegate void IDutsRecvDataHandle(byte[] data, int portId, int ipId);
    public class DutConn
    {
        private UdpConfig _config;
        private UdpServer _udpConn;
        public UdpServer Conn { get { return _udpConn; } }
        private int _portIndex;
        private bool _isRun;
        public delegate void IDutsRecvDataHandle(byte[] data, int portId, int ipId);
        private IDutsRecvDataHandle _RecvDataHandle;
        public DutConn(int portIndex, IDutsRecvDataHandle dataHandle)
        {
            _config = new UdpConfig(portIndex, OnConfigChange);
            _udpConn = new UdpServer(OnDutsDatasReceive);
            _portIndex = portIndex;
            _RecvDataHandle = dataHandle;
            _isRun = false;
        }

        public bool Start(ref string errMsg)
        {
            if (_isRun)
            {
                return _isRun;
            }
            _isRun = _udpConn.Start(ushort.Parse(_config.RxPort));
            if (_isRun)
            {
                errMsg = String.Format(@"启动接收端口:{0}成功", _config.RxPort);
            }
            else
            {
                errMsg = String.Format(@"启动接收端口:{0}失败", _config.RxPort);
            }
            return _isRun;
        }
        public void Stop()
        {
            _udpConn.Stop();
            _isRun = false;
        }
        private void  OnConfigChange()
        {
            Hlog.I(string.Format(@"udp port {0}config change.", _portIndex));
            if (_isRun)
            {
                string errorMsg = "";
                _udpConn.Stop();
                if (!Start(ref errorMsg))
                {
                    Hlog.E(string.Format(@"udp recv port {0} create fail..", _config.RxPort));
                }
            }  
        }

        private bool OnDutsDatasReceive(byte[] data, IPEndPoint ipPoint)
        {
            int ipIndex = _config.ParseIpIndex(ipPoint.Address.ToString());
            if (ipPoint.Address.ToString() == "127.0.0.1")// 方便调试
            {
                ipIndex = 0;
            }
            if (_RecvDataHandle != null)
            {
                _RecvDataHandle(data, _portIndex, ipIndex);
            }
            return true;
        }
    }
}
