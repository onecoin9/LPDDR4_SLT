using Hsg.Common;
using Hsg.Common.ADO;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.config
{
    class BSTeamConfig
    {
        public static int DUTS_COUNT = SysConfig.PORT_NUM * SysConfig.TEAM_GROUP_NUM;
        public static int GROUP_COUNT = SysConfig.TEAM_GROUP_NUM;
        public static int ITEM_DUT_NUM = SysConfig.PORT_NUM;
        private int _ipIndex;
        private SysConfig _sysConfig;
        private bool _bConfigChange;
        private IOnMemberChange _onConfigChange;
        private int _dutOrder;
        public int Timeout
        {
            get; set;
        }
        public string GroupAIpAddr
        {
            get { return _sysConfig.GroupAIp.GetItemValue(_ipIndex); }
        }
        public UInt32 RepeatIntervalSec
        {
            get { return UInt32.Parse(_sysConfig.RepeatIntervalSec.Value); }
        }
        public string GroupBIpAddr
        {
            get { return _sysConfig.GroupBIp.GetItemValue(_ipIndex); }
        }
        public int dutOrder
        {
            get { return _dutOrder; }
        }
        public int DutConnectTimeoutSecond
        {
            get { return int.Parse(_sysConfig.DutConnectTimeout.Value); }
        }
        public int TeamExecSpanTime
        {
            get { return int.Parse(_sysConfig.TeamExecTmSpan.Value); }
        }
        public int HightTempPrepareSecond
        {
            get { return int.Parse(_sysConfig.HightTempWaitTimeout.Value); }
        }
        public int NormalTempPrepareSecond
        {
            get { return int.Parse(_sysConfig.NormalTempWaitTimeout.Value); }
        }
        public int AbnormalWaitSecond // 异常等待时间
        {
            get { return int.Parse(_sysConfig.AbnormalWaitSecond.Value); }
        }
        /* public bool DebugAutoRetry
           {
               get { return _sysConfig.DebugAutoRetry.Value == "1"; }
           }*/
        public bool OpenTempMgr
        {
            get { return SysConfig.TempState == (byte)TempState.TmpHight || SysConfig.TempState == (byte)TempState.TmpMixture; }
        }
        public UInt32 ExcuteFrequency
        {
            get; set;
        }
        public bool OrderBinByStage// 按照 段分BIN
        {
            get { return _sysConfig.OrderBinByStage.CheckBoolValue(); }
        }
        public bool DiagnosticMode
        {
            get { return _sysConfig.DiagnosticMode.CheckBoolValue(); }
        }

        public bool TempCtrInitAllEnable
        {
            get { return _sysConfig.TempCtrInitAllEnable.CheckBoolValue(); }
        }

        public bool IdlePowerHold
        {
            get { return _sysConfig.IdlePowerHold.CheckBoolValue(); }
        }
        public int RetryMaxFailCount
        {
            get; set;
        }
        public bool RetryResultOptimization
        {
            get; set;
        }
        public BSTeamConfig(Int32 ipIndex, IOnMemberChange onConfigChange)
        {
            _ipIndex = ipIndex;
            _sysConfig = SysConfig.GetInstance();
            _dutOrder = Int32.Parse(_sysConfig.DutOrder.Value);
            _sysConfig.GroupAIp.BindOnMemberChange(OnMemberChange, ipIndex);
            _sysConfig.GroupBIp.BindOnMemberChange(OnMemberChange, ipIndex);
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

        public int GetEnvTempWaitTimeout(TempState state)
        {
            if(state == TempState.TmpHight)
            {
                return HightTempPrepareSecond;
            }
            else
            {
                return NormalTempPrepareSecond; ;
            }
        }
    }
}
