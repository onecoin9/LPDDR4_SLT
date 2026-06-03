using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.config
{
    public class MBConfig
    {
        private int _ipIndex;
        private int _groupId;
        private SysConfig _sysConfig;
        private bool _bConfigChange;
        private IOnMemberChange _onConfigChange;
        public string ipAddr
        {
            get
            {
                if(_groupId == 0)
                {
                    return _sysConfig.GroupAIp.GetItemValue(_ipIndex);
                } else
                {
                    return _sysConfig.GroupBIp.GetItemValue(_ipIndex);
                }
            }
        }
        public int remotePort
        {
            get { return int.Parse(_sysConfig.MbTxPort.Value); }
        }
        public int localPort
        {
            get { return int.Parse(_sysConfig.MbRxPort.Value); }
        }
        public byte slaveId
        {
            get { return byte.Parse(_sysConfig.MbSlaveAddr.Value); }
        }
        public String BoardProtocol
        {
            get { return _sysConfig.BoardProtocol.Value; }
        }
        public MBConfig(int ipIndex, int groupId, IOnMemberChange onConfigChange)
        {
            _ipIndex = ipIndex;
            _sysConfig = SysConfig.GetInstance();
            // 根据group 调整
            if(groupId == 0)
            {
                _sysConfig.GroupAIp.BindOnMemberChange(OnMemberChange, ipIndex);
            }
            else
            {
                _sysConfig.GroupBIp.BindOnMemberChange(OnMemberChange, ipIndex);
            }
            _groupId = groupId;
            _sysConfig.MbTxPort.DetectOnValueChange(OnMemberChange);
            _sysConfig.MbRxPort.DetectOnValueChange(OnMemberChange);
            _sysConfig.MbSlaveAddr.DetectOnValueChange(OnMemberChange);
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
