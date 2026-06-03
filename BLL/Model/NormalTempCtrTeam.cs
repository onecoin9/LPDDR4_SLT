using Hsg.BLL.TempCtr;
using Hsg.Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.Model
{
    public partial class NormalTempCtrTeam
    {

        /// <summary>
        ///  启动温控
        /// </summary>
        /// <param name="dutFlag">uint32 每一位代表一个dut 是否使用1使用，0，不使用</param>
        public void StartWork()
        {
            ChangeVolStage(true);
            PostEventAsync(TempCtrEvent.EVT_RESET_EVT);
        }
        /// <summary>
        /// 进入测试模式
        /// </summary>
        public void EntryTestMode()
        {
            Hlog.I(Mod, "EntrTestMode lock abnormal");
        }

        //public bool Enable { get { return CurState > TempCtrState.STATE_INIT; } } // 是否开启温控管理
        public void WaitTempStabilityTimeout()
        {
            if (CurState == TempCtrState.STATE_PREPARE)
            {
                _clientConn.CancelResponse();
                PostEventAsync(TempCtrEvent.EVT_WAIT_TIMEOUT);
            }
            else
            {
                Hlog.W(Mod, "stability timeout invalid for state:" + CurState);
            }
        }

        /// <summary>
        /// 用于测试完成后自动刷新
        /// </summary>
        public void ExitTestMode()
        {
            Hlog.I(Mod, "ExitTestMode unlock abnormal");
            //_AbnormalLock = false;
            //  PostEventAsync(TempCtrEvent.EVT_REFRESH_ABNORMAL);
        }
        public bool CheckDutEnvReady(int dutId, ref float value)
        {
            lock (_stageLock)
            {
                if (_cbPwrStage != VoltageStage.Ready)
                {
                    value = 0;
                    return false;
                }
            }
            if (_dutTempStateList[dutId].state == TempCtrState.STATE_WORKING)
            {
                value = _dutTempStateList[dutId].value;
                return true;
            }
            value = _dutTempStateList[dutId].value;
            return false;
        }
        public bool CheckEnvIsReady()
        {
            lock (_stageLock)
            {
                if (_cbPwrStage != VoltageStage.Ready)
                {
                    return false;
                }
            }
            return CurState == TempCtrState.STATE_WORKING;
        }
        public bool CheckVoltageIsReady()
        {
            lock (_stageLock)
            {
                if (_cbPwrStage != VoltageStage.Ready)
                {
                    return false;
                }
            }
            return true;
        }

        public void GetFanSpeed(ref ushort[] speeds)
        {
            speeds = new ushort[TempProtocol.ONE_TEAM_FAN_NUM];
            for (int i = 0; i < TempProtocol.ONE_TEAM_FAN_NUM; i++)
            {
                speeds[i] = _fansStateList[i].value;
            }
        }
        public bool Set5VSwitchOnOff(bool isOn)
        {
            ChangeVolStage(isOn);
            PostEventAsync(TempCtrEvent.EVT_SET_5V_ON_OFF, isOn);
            bool ret = _voltageWaiter.WaitTaskDone(6000);//等待最多不超过6S
            return ret;
        }
        public void RsetEnvironment()
        {
            ChangeVolStage(true);
            PostEventAsync(TempCtrEvent.EVT_RESET_EVT);
        }
        public void Exit()
        {
            PostEventAsync(TempCtrEvent.EVT_EXIT);
        }

        //public bool VoltageStateIsReady()
        //{
        //    lock (_stageLock)
        //    {
        //        if (_cbPwrStage == VoltageStage.Ready)
        //        {
        //            return true;
        //        }
        //    }
        //    return false;
        //}

        public string GetVoltageInfor()
        {
            string info = "";
            lock (_stageLock)
            {
                info = _voltageStateInfo;
            }
            return info;
        }

        public string GetStateInfo()
        {
            switch (StateCode)
            {
                case AbnormalCode.FanSpeed:
                    ushort[] speeds = new ushort[0];
                    GetFanSpeed(ref speeds);
                    return $"风扇异常:{speeds[0]},{speeds[1]},{speeds[2]},{speeds[3]}";
                case AbnormalCode.SndFail://请求失败
                    return $"温控异常:通信故障";
                case AbnormalCode.Voltage://电压不到位
                    string info = GetVoltageInfor();
                    return $"温控异常:电压不到位 " + info;
            }
            if (_cbPwrStage != VoltageStage.Ready)
            {
                string info = GetVoltageInfor();
                return $"温控异常:电压不到位 " + info;
            }
            return "温控正常";
        }

        public bool SyncDutsEnableState(bool[] enableStatus)
        {
            return false;
        }
    }
}
