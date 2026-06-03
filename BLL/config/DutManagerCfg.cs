using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.config
{
    class DutManagerCfg
    {
        private int _teamIndex;
        private SysConfig _sysConfig;
        private bool _bConfigChange;
        private IOnMemberChange _onConfigChange;
        private int _dutOrder;
        private int _groupId;
        public bool Selected { get; set; }
        //public int Timeout
        //{
        //    get { return Int32.Parse(_sysConfig.Timeout.Value); }
        //}
        public UInt16 IOCtrAId
        {
            get { return UInt16.Parse(_sysConfig.IOCtrAId.Value); }
        }
        public UInt16 IOCtrAStart
        {
            get { return UInt16.Parse(_sysConfig.IOCtrAStart.Value); }
        }
        public UInt16 IOCtrASpan
        {
            get { return UInt16.Parse(_sysConfig.IOCtrASpan.Value); }
        }
        public UInt16 IOCtrBatch
        {
            get { return UInt16.Parse(_sysConfig.IOCtrBatch.Value); }
        }
        public UInt16 IOCtrSetMaxLine
        {
            get { return (UInt16)SysConfig.PORT_NUM; }
        }

        private ushort _ioCtrSetIntervalSec;
        public ushort IOCtrSetIntervalSec
        {
            get { return _ioCtrSetIntervalSec; }
        }

        //public bool RepeatTest
        //{
        //    get { return SysConfig.ExecuteFrequency > 1; }
        //}

        public string IpAddr
        {
            get
            {
                if (_groupId == 0)
                {
                    return _sysConfig.GroupAIp.GetItemValue(_teamIndex);
                }
                else
                {
                    return _sysConfig.GroupBIp.GetItemValue(_teamIndex);
                }
            }
        }
        public int IPIndex
        {
            get { return _sysConfig.GetIpIndex(_teamIndex, _groupId); }
        }
        //public string GroupBIpAddr
        //{
        //    get { return _sysConfig.GroupBIp.GetItemValue(_teamIndex); }
        //}
        public int dutOrder
        {
            get { return _dutOrder; }
        }
        public int DutConnectTimeoutSecond
        {
            get { return int.Parse(_sysConfig.DutConnectTimeout.Value); }
        }

        public bool DiagnosticMode
        {
            get
            {
                return _sysConfig.DiagnosticMode.CheckBoolValue();
            }
        }
        
        public DutManagerCfg(Int32 teamId, int groupId, IOnMemberChange onConfigChange)
        {
            _teamIndex = teamId ;
            _sysConfig = SysConfig.GetInstance();
            _dutOrder = Int32.Parse(_sysConfig.DutOrder.Value);
            _ioCtrSetIntervalSec = 0;
            ushort.TryParse(_sysConfig.DutsIOSetIntervalSec.Value, out _ioCtrSetIntervalSec);
            Selected = true;
            _groupId = groupId ;
            if (groupId == 0)
            {
                _sysConfig.GroupAIp.BindOnMemberChange(OnMemberChange, teamId);
            }
            else
            {
                _sysConfig.GroupBIp.BindOnMemberChange(OnMemberChange, teamId);
            }

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
        public int ConventIdToBoard(int dutIndex)
        {
            int line = 0;
            if (dutOrder == SysConfig.DUT_ORDER_RIGHT_TO_LEFT)
            {
                line = (byte)(SysConfig.PORT_NUM - 1 - dutIndex);
            }
            else
            {
                line = (byte)dutIndex;
            }
            return line;
        }
    }
}
