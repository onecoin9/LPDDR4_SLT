using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading.Tasks;
using TBM01.BLL.config;
using TBM01.BLL.Net;
using TBM01.Common;

namespace TBM01.BLL
{
    public delegate void IDutsRecvDataHandle(byte[] data, int portId, int ipId);
    public class DutsReceiver
    {
        private UdpReceiverConfig _config;
        private UdpReceiver _receiver;
        private int _portIndex;
        private bool _isRun;
        private IDutsRecvDataHandle _RecvDataHandle;
        public DutsReceiver(int portIndex, IDutsRecvDataHandle dataHandle)
        {
            _config = new UdpReceiverConfig(portIndex, OnConfigChange);
            _receiver = new UdpReceiver(OnDutsDatasReceive);
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
            _isRun = _receiver.start(Int32.Parse(_config.RxPort));
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
            _receiver.stop();
            _isRun = false;
        }
        private void  OnConfigChange()
        {
            Hlog.I(string.Format(@"udp port {0}config change.", _portIndex));
            if (_isRun)
            {
                string errorMsg = "";
                _receiver.stop();
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
