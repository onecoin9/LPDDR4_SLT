using Hsg.BLL.config;
using Hsg.Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading.Tasks;
using static Hsg.BLL.DutMaster;

namespace Hsg.BLL.Service
{
    public class TBCommunicateSvr
    {
        private List<DutConn> _dutsConnList;
        private Action<int, Byte[]>[] _dataHandler;
        private SysConfig _sysConfig;
        private static readonly object _classLock = new object();
        private static TBCommunicateSvr _handler;
        public bool ServerIsReady { get; private set; }
        public static TBCommunicateSvr GetInstance()
        {
            if (_handler == null)
            {
                lock (_classLock)
                {
                    if (_handler == null)
                    {
                        _handler = new TBCommunicateSvr();
                    }
                }
            }
            return _handler;
        }
        private TBCommunicateSvr()
        {
            _dutsConnList = new List<DutConn>();
            _sysConfig = SysConfig.GetInstance();
            for (int i = 0; i < SysConfig.PORT_NUM; i++)
            {
                DutConn receiver = new DutConn(i, OnDutsDatasReceive);
                _dutsConnList.Add(receiver);
            }
            _dataHandler = new Action<int, byte[]>[SysConfig.DEV_NUM * SysConfig.TEAM_GROUP_NUM];
        }
        public bool StartService(ref string error)
        {
            bool hadError = false;
            for (int i = 0; i < _dutsConnList.Count; i++)
            {
                string result = "";
                if (!_dutsConnList[i].Start(ref result))
                {
                    if (error.Length > 0)
                    {
                        error += "\r\n";
                    }
                    error += result;
                    hadError = true;
                }
            }
            if (!hadError)
            {
                ServerIsReady = true;
            }
            return hadError;
        }
        public void StopService()
        {
            for (int i = 0; i < _dutsConnList.Count; i++)
            {
                _dutsConnList[i].Stop();
            }
        }
        public bool RegistDataHandle(Action<int, byte[]> dataHandler, string ipAddr)
        {
            int index = _sysConfig.GetIpIndex(ipAddr);
            if (index >= 0)
            {
                _dataHandler[index] = dataHandler;
                return true;
            }
            return false;
        }
        private void OnDutsDatasReceive(byte[] data, int portIndex, int ipIndex)
        {
            if (ipIndex >= 0)
            {
                int gropuId = ipIndex / SysConfig.DEV_NUM;
                if (ipIndex < _dataHandler.Length)
                {
                    _dataHandler[ipIndex]?.Invoke(portIndex, data);
                }
                //if(_teamList[ipIndex].OnDutsDataHanlde(data, portIndex))
                //{
                //   // AppendLogToUi(string.Format(@"接收到板卡{0}-{1}的数据:{2}", ipIndex + 1, portIndex + 1, Tools.HexToString(data)), LOG_TYPE.INFO);
                //}
            }
            else
            {
                // AppendLogToUi(string.Format(@"接收到板卡{0}-{1}无效数据:{2}", ipIndex + 1, portIndex + 1, Tools.HexToString(data)), LOG_TYPE.ERROR);
            }
        }
    }

}
