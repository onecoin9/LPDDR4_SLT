using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL
{
    public class TcpClientConfig
    {
        private SysConfig _sysConfig;
        private bool _bConfigChange;
        private IOnMemberChange _onConfigChange;
        public string DestIp
        {
            get { return _sysConfig.DestIp.Value; }
        }
        public ushort DestPort
        {
            get { return ushort.Parse(_sysConfig.DestPort.Value); }
        }
        public ushort HandlerReplyPort
        {
            get { return ushort.Parse(_sysConfig.HandlerReplyPort.Value); }
        }
        public TcpClientConfig(IOnMemberChange onConfigChange)
        {
            _sysConfig = SysConfig.GetInstance();
            _sysConfig.DestIp.DetectOnValueChange(OnMemberChange);
            _sysConfig.DestPort.DetectOnValueChange(OnMemberChange);
            _sysConfig.HandlerReplyPort.DetectOnValueChange(OnMemberChange);
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
