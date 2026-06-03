using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.config
{
    public class UdpSenderConfig
    {
        private int _ipIndex;
        private int _groupId;
        private int _portIndex;
        private SysConfig _sysConfig;
        private bool _bConfigChange;
        private IOnMemberChange _onConfigChange;
        public string IP
        {
            get
            {
                if(_groupId == 0)
                {
                    return _sysConfig.GroupAIp.GetItemValue(_ipIndex);
                }
                else
                {
                    return _sysConfig.GroupBIp.GetItemValue(_ipIndex);
                }
            }
        }
        public string TxPort
        {
            get { return _sysConfig.TxPort.GetItemValue(_portIndex); }
        }
        public UdpSenderConfig(int ipIndex,int groupId, int portIndex, IOnMemberChange onConfigChange)
        {
            _ipIndex = ipIndex;
            _groupId = groupId;
            _sysConfig = SysConfig.GetInstance();
            if(_groupId == 0)
            {
                _sysConfig.GroupAIp.BindOnMemberChange(OnMemberChange, ipIndex);
            } else
            {
                _sysConfig.GroupBIp.BindOnMemberChange(OnMemberChange, ipIndex);
            }
            if (Int32.Parse(_sysConfig.DutOrder.Value) == SysConfig.DUT_ORDER_RIGHT_TO_LEFT)
            {
                _portIndex = SysConfig.PORT_NUM - 1 -  portIndex;
            }
            else
            {
                _portIndex = portIndex;
            }
            
            _sysConfig.TxPort.BindOnMemberChange(OnMemberChange, portIndex);
            _sysConfig.OnConfigUpdate += NotifyConfigUpdate;
            _onConfigChange = onConfigChange;
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
