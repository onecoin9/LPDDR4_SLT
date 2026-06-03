using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace TBM01.BLL.config
{
    public class UdpReceiverConfig
    {
        private int _portIndex;
        private SysConfig _sysConfig;
        private bool _bConfigChange;
        private IOnMemberChange _onConfigChange;

        public string RxPort
        {
            get { return _sysConfig.RxPort.GetItemValue(_portIndex); }
        }
        public UdpReceiverConfig(int portIndex, IOnMemberChange onConfigChange)
        {
            _sysConfig = SysConfig.GetInstance();
            _portIndex = portIndex;
            // 逆序
            if (Int32.Parse(_sysConfig.DutOrder.Value) == SysConfig.DUT_ORDER_RIGHT_TO_LEFT)
            {
                _portIndex = (SysConfig.PORT_NUM -1 - _portIndex);
            }
            _sysConfig.RxPort.BindOnMemberChange(OnMemberChange, _portIndex);
            _sysConfig.OnConfigUpdate += NotifyConfigUpdate;
            _onConfigChange = onConfigChange;
        }
        public int ParseIpIndex(string ip)
        {
            return _sysConfig.GetIpIndex(ip);
        }
        private void OnMemberChange()
        {
            _bConfigChange = true;
        }
        /// <summary>
        /// 通知配置信息修改
        /// </summary>
        private void NotifyConfigUpdate()
        {
            if (_onConfigChange != null && _bConfigChange)
            {
                _bConfigChange = false;
                _onConfigChange();
            }

        }
    }
}
