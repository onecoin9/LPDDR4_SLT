using Hsg.BLL.config;
using Hsg.BLL.TempCtr;
using Hsg.Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Hsg.BLL.Model
{
    // 风扇状态 
    public partial class NormalTempCtrTeam : StateMechine<TempCtrState, TempCtrEvent>, TempCtrTeam
    {
        private TempCtrBoardClient _clientConn;
        private TempCtrBoardConfig _config;
        private int _instanceId;
        private bool _startConn;
        private const int MAX_RETRY_TM = 6;
        private const byte MAX_STATE_COUNT = 3;// 最大状态计数，达到次数更改状态
        private int _retryTimerId = TimerTask.INVALID_TIMER_ID;
        private int _onceRetryTime = TimerTask.INVALID_TIMER_ID;
        private int _retryCount;
        private TempCtrEvent _retryEvent;
        private bool _waitEventRetry;// 是否等待中
        private readonly object _waitLock = new object();
        private readonly object _stageLock = new object();
        private TimerTask _timerTask;
        //private bool _AbnormalLock;// 锁住异常
        //private bool _set5VStateDone;
        private bool _setCBPwrIsOn = true;// 设定通讯板电源否需要开启 默认开启5V
        private int _voltageSetTimer = TimerTask.INVALID_TIMER_ID;// 设置电压定时器
        private VoltageStage _cbPwrStage = VoltageStage.Adjusting;// 通讯板电压状态
        private int _heatbeatTimer = TimerTask.INVALID_TIMER_ID;// 设置电压定时器
        private TaskWaiter _voltageWaiter;// 等待电压设定
        public AbnormalCode StateCode
        {
            get; internal set;
        }
        private TempDutInfo[] _dutTempStateList;// 每个dut 温控状态
        private FanInfo[] _fansStateList;// 每个风扇的状态
        private Action<TempCtrState> _onStateChange;
        private string _faultCode;// 故障码
        private string _voltageStateInfo;// 电压环境
        private string _currentStateInfo;// 电压环境
        private bool _fanStabilityWait;// 等待风扇稳定
        public NormalTempCtrTeam(int instanceId, Action<TempCtrState> onStateChange,
                                          Action<int, TempCtrState, float> onDutsStateChange,
                                          Action<int, float> onDutsValueChange) : base("TempCtrTeam" + (instanceId + 1).ToString())
        {
            _instanceId = instanceId;
            _startConn = false;
            _waitEventRetry = false;
            _faultCode = "";
            //  _startFromWrokMode = false;
            _timerTask = TimerTask.GetTimerTaskInstance();
            _config = new TempCtrBoardConfig(instanceId);
            _clientConn = new TempCtrBoardClient(_config, OnRecvResponseHandle);
            // _dutEnableFlag = new bool[TempProtocol.ONE_TEAM_DUT_NUM];
            _dutTempStateList = new TempDutInfo[TempProtocol.ONE_TEAM_DUT_NUM];
            for (int i = 0; i < TempProtocol.ONE_TEAM_DUT_NUM; i++)
            {
                _dutTempStateList[i]._id = i;
                _dutTempStateList[i]._onStateChange += onDutsStateChange;
                _dutTempStateList[i]._onValueChange += onDutsValueChange;
            }
            _fansStateList = new FanInfo[TempProtocol.ONE_TEAM_FAN_NUM];
            _onStateChange += onStateChange;
            _voltageWaiter = new TaskWaiter();
            RegisterActionHandle();
        }
        public override void Run()
        {
            StartSync(TempCtrState.STATE_INIT);
        }
        protected override void NotifyStateChange(TempCtrState state)
        {
            switch (state)
            {
                case TempCtrState.STATE_INIT:
                    DoInitStateInit();
                    break;
                case TempCtrState.STATE_PREPARE:
                    DoPrepareStateInit();
                    break;
                case TempCtrState.STATE_ABNORMAL:
                    DoAbnormalStateInit();
                    break;
                case TempCtrState.STATE_WORKING:
                    DoWorkingStageInit();
                    break;
            }
            _onStateChange?.Invoke(state);
        }
        private void RegisterActionHandle()
        {
            // RegisterStateHandle(TempCtrState.STATE_INIT, TempCtrEvent.EVT_START_HIGHT_TEMP_MODE, DoActionStartHightTempMode);
            RegisterStateHandle(TempCtrState.STATE_INIT, TempCtrEvent.EVT_CONN_CHECK, DoActionConnectStateCheck);
            RegisterStateHandle(TempCtrState.STATE_INIT, TempCtrEvent.EVT_EXIT, DoActionDestory);

            RegisterStateHandle(TempCtrState.STATE_PREPARE, TempCtrEvent.EVT_SET_FAN_SPEED, DoActionSetFunSpeed);
            RegisterStateHandle(TempCtrState.STATE_PREPARE, TempCtrEvent.EVT_CHECK_FAULT, DoActionCheckFault);
            RegisterStateHandle(TempCtrState.STATE_PREPARE, TempCtrEvent.EVT_WAIT_STABILITY, DoActionWaitStability);
            RegisterStateHandle(TempCtrState.STATE_PREPARE, TempCtrEvent.EVT_GET_FAN_SEPPED, DoActionGetFunSpeed);
            RegisterStateHandle(TempCtrState.STATE_PREPARE, TempCtrEvent.EVT_WAIT_TIMEOUT, DoActionWaitStabilityTimeout);
            RegisterStateHandle(TempCtrState.STATE_PREPARE, TempCtrEvent.EVT_RESET_EVT, DoActionPrepareResetEvt);
            RegisterStateHandle(TempCtrState.STATE_PREPARE, TempCtrEvent.EVT_5V_ADJUSTING_DONE, DoActionPrepareSwitch5VDone);
            RegisterStateHandle(TempCtrState.STATE_PREPARE, TempCtrEvent.EVT_EXIT, DoActionDestory);

            RegisterStateHandle(TempCtrState.STATE_WORKING, TempCtrEvent.EVT_EXIT, DoActionDestory);
            RegisterStateHandle(TempCtrState.STATE_WORKING, TempCtrEvent.EVT_RESET_EVT, DoActionWorkingResetEvt);
            RegisterStateHandle(TempCtrState.STATE_WORKING, TempCtrEvent.EVT_5V_ADJUSTING_DONE, DoActionWorkingSwitch5VDone);
            RegisterStateHandle(TempCtrState.STATE_WORKING, TempCtrEvent.EVT_IDLE_HEATBEAT, DoActionIdleHeatbeat);
            RegisterStateHandle(TempCtrState.STATE_WORKING, TempCtrEvent.EVT_SET_5V_ON_OFF, DoActionSwitch5V);
            RegisterStateHandle(TempCtrState.STATE_WORKING, TempCtrEvent.EVT_5V_ABNORMAL, DoActionWorkingVoltateAbnormal);


            RegisterStateHandle(TempCtrState.STATE_ABNORMAL, TempCtrEvent.EVT_RESET_EVT, DoActionStartWorkMode);
            RegisterStateHandle(TempCtrState.STATE_ABNORMAL, TempCtrEvent.EVT_EXIT, DoActionDestory);
            RegisterStateHandle(TempCtrState.STATE_ABNORMAL, TempCtrEvent.EVT_SET_5V_ON_OFF, DoActionSwitch5V);

            // 全局事件处理
            //RegisterAllStateHandle(TempCtrEvent.EVT_SET_5V_ON_OFF, DoActionSwitch5V);
            RegisterAllStateHandle(TempCtrEvent.EVT_5V_ADJUSTING, DoActionVoltageAdjust);

        }

        #region state init
        private void DoInitStateInit()
        {
            if (!_startConn)
            {
                _startConn = true;
                _clientConn.StartConn();
                Hlog.I(Mod, "StartConn");
            }
            _fanStabilityWait = false;
            PostEventAsync(TempCtrEvent.EVT_CONN_CHECK);
        }
        private void DoPrepareStateInit()
        {
            StopRetryTimer();
            for (int i = 0; i < _dutTempStateList.Length; i++)
            {
                _dutTempStateList[i].stateCount = 0;
                _dutTempStateList[i].state = TempCtrState.STATE_PREPARE;
                _dutTempStateList[i].StateCode = AbnormalCode.None;
            }
            for (int i = 0; i < _fansStateList.Length; i++)
            {
                _fansStateList[i].state = TempCtrState.STATE_PREPARE;
                _fansStateList[i].StateCode = AbnormalCode.None;
                _fansStateList[i].stateCount = 0;
                _fansStateList[i].value = 0;
            }
            _fanStabilityWait = false;
            StateCode = AbnormalCode.None;
            PostEventAsync(TempCtrEvent.EVT_SET_FAN_SPEED);
        }

        private void DoAbnormalStateInit()
        {
            StopRetryTimer();
            IdleHeatbeatTimerStop();
            VoltageCheckTimerDone();
            _fanStabilityWait = false;
            for (int i = 0; i < _fansStateList.Length; i++)
            {
                _fansStateList[i].state = TempCtrState.STATE_ABNORMAL;
            }
            UpdateAllDutTempStage(TempCtrState.STATE_ABNORMAL, AbnormalCode.WaitStabilityTimeout);
        }

        private void DoWorkingStageInit()
        {
            UpdateAllDutTempStage(TempCtrState.STATE_WORKING, AbnormalCode.None);
            IdleHeatbeatTimerStart();
        }
        #endregion
        #region STATE EVENT HDR
        private TempCtrState DoActionStartWorkMode(object param)
        {
            StopRetryTimer();
            if (!_clientConn.Connected)
            {
                return TempCtrState.STATE_INIT;
            }
            return TempCtrState.STATE_PREPARE;
        }

        private TempCtrState DoActionConnectStateCheck(object param)
        {
            if (!_clientConn.Connected)
            {
                StartRetryTimer(3000, TempCtrEvent.EVT_CONN_CHECK);
                return TempCtrState.STATE_INIT;
            }
            return TempCtrState.STATE_PREPARE;
        }

        //private TempCtrState DoActionpRrepareSwitch5V(object param)
        //{
        //    _voltageStateInfo = "";
        //    _currentStateInfo = "";
        //    if (CurState == TempCtrState.STATE_INIT)// 准备状态不执行
        //    {
        //        return CurState;
        //    }
        //    return TempCtrState.STATE_PREPARE;
        //}
        //static bool WaitForSemaphore(Semaphore semaphore, int timeoutMs)
        //{
        //    bool acquired = false;
        //    try
        //    {
        //        // 尝试获取信号量  
        //        acquired = semaphore.WaitOne(timeoutMs);
        //    }
        //    catch (ArgumentException)
        //    {
        //        // Console.WriteLine("Invalid timeout value");
        //    }
        //    //  Console.WriteLine("@@@@ WaitForSemaphore:" + acquired);
        //    return acquired;
        //}

        private TempCtrState DoActionPrepareSwitch5VDone(object param)
        {
            PostEventAsync(TempCtrEvent.EVT_GET_FAN_SEPPED);// 开始查询风扇
            return TempCtrState.STATE_PREPARE;
        }
        private TempCtrState DoActionWorkingSwitch5VDone(object param)
        {
            return TempCtrState.STATE_WORKING;
        }

        private TempCtrState DoActionWoringSwitch5VDone(object param)
        {
            //PostEventAsync(TempCtrEvent.EVT_GET_FAN_SEPPED);// 开始查询风扇
            return TempCtrState.STATE_PREPARE;
        }

        private TempCtrState DoActionSwitch5V(object param) // 只用于就绪状态
        {
            _voltageStateInfo = "";
            _currentStateInfo = "";
            lock (_stageLock)
            {
                _cbPwrStage = VoltageStage.Adjusting;
            }
            VoltageCheckTimerStart();
            return CurState;
        }


        private TempCtrState DoActionVoltageAdjust(object param)
        {
            if (_cbPwrStage == VoltageStage.Adjusting)
            {
                TempCtrRet ret = _clientConn.Set5VOnOff(_setCBPwrIsOn);
                if (ret != TempCtrRet.ok)
                {
                    Hlog.D(Mod, "send faile:" + ret.ToString());
                }
            }
            else if (_cbPwrStage == VoltageStage.Checking)
            {
                TempCtrRet ret = _clientConn.QueryVoltage();
                if (ret != TempCtrRet.ok)
                {
                    Hlog.D(Mod, "send faile:" + ret.ToString());
                }
            }
            return CurState;
        }



        private TempCtrState DoActionPrepareResetEvt(object param)
        {
            StopRetryTimer();
            return DoActionSetFunSpeed(param);
        }

        private TempCtrState DoActionWorkingResetEvt(object param)
        {
            PostEventAsync(TempCtrEvent.EVT_SET_5V_ON_OFF);
            return TempCtrState.STATE_WORKING;
        }

        //private TempCtrState DoActionSetTemp(object param)
        //{
        //    TempCtrRet ret = TempCtrRet.ok;
        //    if (_retryCount < MAX_RETRY_TM)
        //    {
        //        StartRetryTimer(2000, TempCtrEvent.EVT_SET_TEMP);
        //        if (_config.UseDiffCompensator)
        //        {
        //            ret = _clientConn.SetTemp(_config.TargetTemp, _config.DutsTempCompensator);
        //        }
        //        else
        //        {
        //            ret = _clientConn.SetTemp(_config.TargetTemp, _config.DefaultTempCompensator);
        //        }
        //        if (ret == TempCtrRet.connect_fail)
        //        {
        //            Hlog.W(Mod, "net discon");
        //        }
        //        else if (ret == TempCtrRet.send_faile)
        //        {
        //            Hlog.W(Mod, "send SetTemp faile.");
        //        }
        //    }
        //    else
        //    {
        //        StateCode = AbnormalCode.SndFail;
        //        return TempCtrState.STATE_ABNORMAL;
        //    }
        //    return TempCtrState.STATE_PREPARE;
        //}
        private TempCtrState DoActionSetFunSpeed(object param)
        {
            TempCtrRet ret = TempCtrRet.ok;
            if (_retryCount < MAX_RETRY_TM)
            {
                StartRetryTimer(2000, TempCtrEvent.EVT_SET_FAN_SPEED);
                ret = _clientConn.SetFanSpeed(_config.TargetSpeed);
            }
            else
            {
                if (ret == TempCtrRet.connect_fail)
                {
                    Hlog.W(Mod, "net discon");
                }
                else if (ret == TempCtrRet.send_faile)
                {
                    Hlog.W(Mod, "send  SetFanSpeed faile.");
                }
                StateCode = AbnormalCode.SndFail;
                return TempCtrState.STATE_ABNORMAL;
            }
            return TempCtrState.STATE_PREPARE;
        }
        private TempCtrState DoActionCheckFault(object param)
        {
            TempCtrRet ret = TempCtrRet.ok;

            if (_retryCount < MAX_RETRY_TM)
            {
                StartRetryTimer(2000, TempCtrEvent.EVT_CHECK_FAULT);
                ret = _clientConn.QueryFault();
                if (ret == TempCtrRet.connect_fail)
                {
                    Hlog.W(Mod, "net discon");
                }
                else if (ret == TempCtrRet.send_faile)
                {
                    Hlog.W(Mod, "send QueryFault faile.");
                }
            }
            else
            {
                StateCode = AbnormalCode.SndFail;
                return TempCtrState.STATE_ABNORMAL;
            }
            return TempCtrState.STATE_PREPARE;
        }

        private TempCtrState DoActionIdleHeatbeat(object param)
        {
            TempCtrRet ret = TempCtrRet.ok;
            if (_cbPwrStage != VoltageStage.Ready)// 电压调整中不需要执行
            {
                return TempCtrState.STATE_WORKING;
            }
            ret = _clientConn.QueryVoltage();
            if (ret == TempCtrRet.connect_fail)
            {
                Hlog.W(Mod, "net discon");
            }
            else if (ret == TempCtrRet.send_faile)
            {
                Hlog.W(Mod, "send QueryFault faile.");
            }
            return TempCtrState.STATE_WORKING;
        }

        private TempCtrState DoActionWorkingVoltateAbnormal(object param)
        {
            StopRetryTimer();
            StateCode = AbnormalCode.Voltage;
            return TempCtrState.STATE_ABNORMAL;
        }

        private TempCtrState DoActionWaitStability(object param)
        {
            //PostEventAsync(TempCtrEvent.EVT_SET_5V_ON_OFF); // 设置5V电源
            VoltageCheckTimerStart();
            return TempCtrState.STATE_PREPARE;
        }

        private TempCtrState DoActionWaitStabilityTimeout(object param)
        {
            StopRetryTimer();
            if (_cbPwrStage != VoltageStage.Ready) // 电压未就绪
            {
                StateCode = AbnormalCode.Voltage;
                return TempCtrState.STATE_ABNORMAL;
            }
            if (!CheckFansStateStability())// 风扇未稳定，标注未风扇故障。
            {
                if (_fanStabilityWait)
                {
                    StateCode = AbnormalCode.FanSpeed;
                }
                else
                {
                    StateCode = AbnormalCode.WaitStabilityTimeout;
                }
                return TempCtrState.STATE_ABNORMAL;
            }
            OnCheckDutsTempStateStabilityTimeout();
            return TempCtrState.STATE_WORKING;
        }

        private TempCtrState DoActionWaitTempStability(object param)
        {
            if (CheckDutsTempStateStability())
            {
                Hlog.W(Mod, "Duts State Stability");
                return TempCtrState.STATE_WORKING;
            }
            TempCtrRet ret = TempCtrRet.ok;

            if (_retryCount < MAX_RETRY_TM)
            {
                StartRetryTimer(2000, TempCtrEvent.EVT_GET_TEMP);
                ret = _clientConn.UpdateTemp();
                if (ret == TempCtrRet.connect_fail)
                {
                    Hlog.W(Mod, "net discon");
                }
                else if (ret == TempCtrRet.send_faile)
                {
                    Hlog.W(Mod, "send UpdateTemp faile.");
                }
            }
            else
            {
                StateCode = AbnormalCode.SndFail;
                return TempCtrState.STATE_ABNORMAL;
            }
            return TempCtrState.STATE_PREPARE;
        }

        //private TempCtrState DoActionRefreshAbnormal(object param)
        //{

        //    return TempCtrState.STATE_WORKING;
        //}

        private TempCtrState DoActionGetFunSpeed(object param)
        {
            if (CheckFansStateStability())
            {
                Hlog.W(Mod, "fans state stability");
                foreach (var v in _fansStateList)
                {
                    if (v.state == TempCtrState.STATE_ABNORMAL)
                    {
                        StateCode = AbnormalCode.FanSpeed;
                        // 存在风扇异常，进入异常状态
                        return TempCtrState.STATE_ABNORMAL;
                    }
                }
                _fanStabilityWait = false;
                return TempCtrState.STATE_WORKING;
            }

            TempCtrRet ret = TempCtrRet.ok;
            _fanStabilityWait = true;
            if (_retryCount < MAX_RETRY_TM)
            {
                StartRetryTimer(2000, TempCtrEvent.EVT_GET_FAN_SEPPED);
                ret = _clientConn.UpdateFanSpeed();
                if (ret == TempCtrRet.connect_fail)
                {
                    Hlog.W(Mod, "net discon");
                }
                else if (ret == TempCtrRet.send_faile)
                {
                    Hlog.W(Mod, "send UpdateFanSpeed faile.");
                }
            }
            else
            {
                StateCode = AbnormalCode.SndFail;
                return TempCtrState.STATE_ABNORMAL;
            }
            return TempCtrState.STATE_PREPARE;
        }
        private TempCtrState DoActionDestory(object param)
        {
            TempCtrRet ret = TempCtrRet.ok;
            int retryCount = 0;
            StopRetryTimer();
            IdleHeatbeatTimerStop();
            VoltageCheckTimerDone();
            if (CurState == TempCtrState.STATE_INIT)
            {
                return TempCtrState.STATE_EXIT;
            }
            do
            {
                if (retryCount > 0)
                {
                    Task.Delay(1000).Wait();
                }
                retryCount++;
                ret = _clientConn.SwitchOffTempCtr();
            } while (ret != TempCtrRet.ok && retryCount < 3);


            return TempCtrState.STATE_EXIT;
        }
        #endregion

        #region timeout retry
        private void StartRetryTimer(int msecond, TempCtrEvent eventId)
        {
            lock (_waitLock)
            {
                _retryTimerId = _timerTask.StartTimer(msecond, false, RetryActionTimeout);
                if (_retryEvent == eventId)
                {
                    _retryCount++;
                }
                else
                {
                    _retryCount = 0;
                    _retryEvent = eventId;
                }
                _waitEventRetry = true;
            }

            if (_retryTimerId == TimerTask.INVALID_TIMER_ID)
            {
                Hlog.E("assign timer id failed");
            }
            //Hlog.I("start retry timer team:" + _instanceId);
        }
        private void StopRetryTimer()
        {
            //   Hlog.D("StopRetryTimer:" + _instanceId);
            lock (_waitLock)
            {
                if (_retryTimerId != TimerTask.INVALID_TIMER_ID)
                {
                    _timerTask.StopTimer(ref _retryTimerId);
                }
                _retryCount = 0;
                _waitEventRetry = false;
                _retryEvent = 0;
            }
        }
        private void RetryActionTimeout(int timerId)
        {
            // Hlog.I(Mod, "retry action timeout team:" + _instanceId);
            lock (_waitLock)
            {
                if (timerId == _retryTimerId)
                {
                    _retryTimerId = TimerTask.INVALID_TIMER_ID;
                    if (_waitEventRetry)
                    {
                        _waitEventRetry = false;
                        PostEventAsync(_retryEvent);
                    }
                }
            }
        }

        private bool ClearWaitTimer(TempCtrEvent evt)
        {
            // Console.WriteLine($"ClearWaitTimer :{evt} {_retryEvent} {_retryTimerId}");
            if (_retryTimerId != TimerTask.INVALID_TIMER_ID)
            {
                lock (_waitLock)
                {
                    if (_waitEventRetry && evt == _retryEvent)
                    {
                        _timerTask.StopTimer(ref _retryTimerId);
                        _retryCount = 0;
                        _waitEventRetry = false;
                        _retryEvent = 0;
                        return true;
                    }
                }
            }
            return false;
        }


        private void IdleHeatbeatTimerStart()
        {
            lock (_waitLock)
            {
                if (_heatbeatTimer == TimerTask.INVALID_TIMER_ID) // 设置为持续
                {
                    _heatbeatTimer = StartTimer(2500, true, TempCtrEvent.EVT_IDLE_HEATBEAT);
                }
            }
        }

        private void IdleHeatbeatTimerStop()
        {
            lock (_waitLock)
            {
                if (_heatbeatTimer != TimerTask.INVALID_TIMER_ID) // 设置为持续
                {
                    StopTimer(ref _heatbeatTimer);
                }
            }
        }

        private void VoltageCheckTimerStart()
        {
            lock (_waitLock)
            {
                if (_voltageSetTimer == TimerTask.INVALID_TIMER_ID) // 设置为持续
                {
                    _voltageSetTimer = StartTimer(2000, true, TempCtrEvent.EVT_5V_ADJUSTING);
                    PostEventAsync(TempCtrEvent.EVT_5V_ADJUSTING);
                }
            }
        }
        private void VoltageCheckTimerDone()
        {
            lock (_waitLock)
            {
                if (_voltageSetTimer != TimerTask.INVALID_TIMER_ID) // 关闭任务
                {
                    StopTimer(ref _voltageSetTimer);
                }
            }
            _voltageWaiter.SetTaskDone();
            if (CurState == TempCtrState.STATE_WORKING) // 通知一下环境就绪
            {
                _onStateChange?.Invoke(CurState);
            }
        }
        #endregion
        private void OnRecvResponseHandle(short respId, byte[] param)
        {
            ushort[] fanSpeed = new ushort[0];
            byte[] tempStatus = new byte[0];
            byte[] fanStatus = new byte[0];
            float[] tempValues = new float[0];
            ushort[] voltage = new ushort[0];
            ushort[] shuntVoltage = new ushort[0];
            // Console.WriteLine("OnRecvResponseHandle respId:" + respId + "paramlen:" + param?.Length);
            switch (respId)
            {
                case TempProtocol.CMD_SET_FAN_SPEED:
                    if (param != null && param.Length >= 1)
                    {
                        if (param[0] == TempProtocol.STATE_CODE_OK)
                        {
                            if (!ClearWaitTimer(TempCtrEvent.EVT_SET_FAN_SPEED))
                            {
                                Hlog.D(Mod, "timeout resp CMD_SET_FAN_SPEED:" + param[0]);
                                return;
                            }
                            PostEventAsync(TempCtrEvent.EVT_CHECK_FAULT);
                        }
                        Hlog.D(Mod, "resp CMD_SET_FAN_SPEED:" + param[0]);
                    }
                    break;
                case TempProtocol.CMD_QUERY_FAULT:
                    Hlog.D(Mod, "resp CMD_QUERY_FAULT:");
                    if (param != null && TempProtocol.DecodeQueryFaultParams(param, ref tempStatus, ref fanStatus))
                    {
                        if (!ClearWaitTimer(TempCtrEvent.EVT_CHECK_FAULT))
                        {
                            Hlog.I(Mod, "timeout resp CMD_QUERY_FAULT");
                            return;
                        }
                        Hlog.I(Mod, "tempStatus:" + Tools.HexToString(tempStatus));
                        Hlog.I(Mod, "fanStatus:" + Tools.HexToString(fanStatus));
                        _faultCode = "tmp:" + Tools.HexToString(tempStatus) + "fan:" + Tools.HexToString(fanStatus);
                        //for (int i = 0; i < TempProtocol.ONE_TEAM_DUT_NUM/8;)
                        //{
                        //    int j = 0;
                        //    for (; j < 8; j++)
                        //    {
                        //        if ((tempStatus[i] & (1 << j)) != 0)
                        //        {
                        //            UpdateDutTempState(i + j, TempCtrState.STATE_ABNORMAL);
                        //        }
                        //    }
                        //    i += 1;
                        //}
                        PostEventAsync(TempCtrEvent.EVT_WAIT_STABILITY); // 进入等待稳定期
                    }
                    break;
                case TempProtocol.CMD_QUERY_VOLTAGE:
                    Hlog.D(Mod, "resp CMD_QUERY_VOLTAGE:");
                    if (param != null && TempProtocol.DecodeVoltageParams(param, ref voltage, ref shuntVoltage))
                    {
                        float tb5v_line0 = (float)voltage[0] / 1000;
                        float tb5v_line1 = (float)voltage[1] / 1000;
                        float tmb12v = (float)voltage[3] / 1000;
                        float fan12v = (float)voltage[5] / 1000;

                        float tb_current0 = ((float)shuntVoltage[0] * 50 / 1000 / 1000);
                        float tb_current1 = ((float)shuntVoltage[1] * 50 / 1000 / 1000);
                        float tmb_current0 = ((float)shuntVoltage[3] * 50 / 1000 / 1000);
                        float fan_current1 = ((float)shuntVoltage[5] * 50 / 1000 / 1000);
                        bool voltageHight = false;
                        bool voltageLow = false;
                        bool voltageAdjustDone = false;
                        bool voltageAbnormal = false;
                        Hlog.D(Mod, "param:" + Tools.HexToString(param));
                        lock (_stageLock)
                        {
                            if (tb5v_line0 >= _config.OutWorkVoltage
                                 && tb5v_line0 < _config.OutWorkVoltage * 1.1
                                 && tb5v_line1 >= _config.OutWorkVoltage
                                 && tb5v_line1 < _config.OutWorkVoltage * 1.1)
                            {
                                voltageHight = true;
                            }
                            else if (tb5v_line0 <= _config.VoltageCloseThreshold && tb5v_line1 <= _config.VoltageCloseThreshold)
                            {
                                voltageLow = true;
                            }
                            if (_cbPwrStage == VoltageStage.Checking) // 
                            {
                                _voltageStateInfo = $"{tb5v_line0},{tb5v_line1},{tmb12v},{fan12v}";
                                _currentStateInfo = $"{tb_current0},{tb_current1},{tmb_current0},{fan_current1}";
                                // Hlog.D(Mod, "voltage:" + _voltageStateInfo);
                                // Hlog.D(Mod, "current:" + _currentStateInfo);
#if _VOLTAGE_DEBUG
                                {
                                   
                                    _cbPwrStage = VoltageStage.Ready;
                                    VoltageCheckTimerDone(); // 注意先改变状态
                                    Hlog.I(Mod, "voltage:" + _voltageStateInfo);
                                    Hlog.I(Mod, "current:" + _currentStateInfo);
                                    PostEventAsync(TempCtrEvent.EVT_5V_ADJUSTING_DONE); // 电压设置完成
                                }
#else
                                if (voltageHight)
                                {
                                    if (_setCBPwrIsOn)
                                    {
                                        _cbPwrStage = VoltageStage.Ready;
                                      //  VoltageCheckTimerDone();
                                        Hlog.I(Mod, "voltage:" + _voltageStateInfo);
                                        Hlog.I(Mod, "current:" + _currentStateInfo);
                                        //PostEventAsync(TempCtrEvent.EVT_5V_ADJUSTING_DONE); // 电压设置完成
                                        voltageAdjustDone = true;
                                    }
                                    else // 重新设置
                                    {
                                        _cbPwrStage = VoltageStage.Adjusting;

                                    }
                                }
                                else if (voltageLow)// 设置为低于0.1v 认为关闭
                                {
                                    if (!_setCBPwrIsOn)
                                    {
                                        _cbPwrStage = VoltageStage.Ready;
       
                                        //VoltageCheckTimerDone();
                                        Hlog.I(Mod, "voltage:" + _voltageStateInfo);
                                        Hlog.I(Mod, "current:" + _currentStateInfo);
                                        //PostEventAsync(TempCtrEvent.EVT_5V_ADJUSTING_DONE); // 电压设置完成
                                        voltageAdjustDone = true;
                                    }
                                    else // 重新设置
                                    {
                                        _cbPwrStage = VoltageStage.Adjusting;
                                        return;
                                    }
                                }
#endif
                            }
                            else if (_cbPwrStage == VoltageStage.Ready)
                            {
                                if (_setCBPwrIsOn) // 电压异常,暂时不处理欠压，只处理断电
                                {
                                    if (voltageLow)
                                    {
                                        _voltageStateInfo = $"{tb5v_line0},{tb5v_line1},{tmb12v},{fan12v}";
                                        _currentStateInfo = $"{tb_current0},{tb_current1},{tmb_current0},{fan_current1}";
                                        //PostEventAsync(TempCtrEvent.EVT_5V_ABNORMAL);
                                        voltageAbnormal = true ;
                                        Hlog.W(Mod, "abnormal voltage:" + _voltageStateInfo);
                                    }
                                    else if (!voltageHight)
                                    {
                                        _voltageStateInfo = $"{tb5v_line0},{tb5v_line1},{tmb12v},{fan12v}";
                                        _currentStateInfo = $"{tb_current0},{tb_current1},{tmb_current0},{fan_current1}";
                                        Hlog.W(Mod, "abnormal voltage:" + _voltageStateInfo);
                                    }
                                }
                            }

                        }
                        
                        if (voltageAdjustDone)
                        {
                            VoltageCheckTimerDone();
                            PostEventAsync(TempCtrEvent.EVT_5V_ADJUSTING_DONE);
                        }

                        if(voltageAbnormal)
                        {
                            PostEventAsync(TempCtrEvent.EVT_5V_ABNORMAL);
                        }

                    }
                    break;
                case TempProtocol.CMD_QUERY_FAN_SPEED:
                    if (param != null && TempProtocol.DecodeFanParams(param, ref fanSpeed))
                    {
                        if (!ClearWaitTimer(TempCtrEvent.EVT_GET_FAN_SEPPED))
                        {
                            Hlog.I(Mod, "timeout resp CMD_QUERY_FAN_SPEED");
                            return;
                        }
                        Hlog.I(Mod, "resp CMD_QUERY_FAN_SPEED:" + Tools.HexToString(param));
                        for (int i = 0; i < fanSpeed.Length; i++)
                        {
                            if (fanSpeed[i] < _config.SpeedLowerLimit) // 转速低于目标速度
                            {
                                SetFanStateCount(i, CountType.OverLowerLimit, fanSpeed[i]);
                            }
                            else
                            {
                                SetFanStateCount(i, CountType.Normal, fanSpeed[i]);
                            }
                        }
                        StartRetryTimer(1000, TempCtrEvent.EVT_GET_FAN_SEPPED);
                    }
                    break;

                case TempProtocol.CMD_SET_VOLTAGE:
                    if (param != null && param.Length >= 1)
                    {
                        if (param[0] == TempProtocol.STATE_CODE_OK)
                        {
                            bool voltageAdjusting = false;
                            // f = true;
                            lock (_stageLock)
                            {
                                if (_cbPwrStage == VoltageStage.Adjusting)
                                {
                                    _cbPwrStage = VoltageStage.Checking;
                                    voltageAdjusting = true;
                                }
                            }
                            if(voltageAdjusting)
                            {
                                PostEventAsync(TempCtrEvent.EVT_5V_ADJUSTING);
                            }
                        }
                        Hlog.D(Mod, "resp CMD_SET_VOLTAGE:" + param[0]);
                    }
                    break;
            }
        }



        private void UpdateDutTempState(int dutId, TempCtrState state, AbnormalCode code)
        {
            if (dutId >= 0 && dutId < _dutTempStateList.Length)
            {
                _dutTempStateList[dutId].StateCode = code;
                _dutTempStateList[dutId].stateCount = 0;
                _dutTempStateList[dutId].value = 0;
                _dutTempStateList[dutId].state = state;
            }
        }

        private void UpdateAllDutTempStage(TempCtrState state, AbnormalCode code)
        {
            for (int dutId = 0; dutId < _dutTempStateList.Length; dutId++)
            {
                _dutTempStateList[dutId].StateCode = code;
                _dutTempStateList[dutId].stateCount = 0;
                _dutTempStateList[dutId].value = 0;
                _dutTempStateList[dutId].state = state;
            }
        }
        private void SetFanStateCount(int funId, CountType type, ushort value)
        {
            if (funId >= 0 && funId < _fansStateList.Length)
            {
                if (_fansStateList[funId].state == TempCtrState.STATE_PREPARE)//  抓正常
                {
                    if (type == CountType.Normal)// 
                    {
                        _fansStateList[funId].value = value;
                        _fansStateList[funId].stateCount = 0;
                        _fansStateList[funId].StateCode = AbnormalCode.None;
                        _fansStateList[funId].state = TempCtrState.STATE_WORKING;
                        return;
                    }
                }
                _fansStateList[funId].value = value;
            }
        }
        private void UpdateFanState(int funId, TempCtrState state)
        {
            if (funId >= 0 && funId < _fansStateList.Length)
            {
                if (state == TempCtrState.STATE_ABNORMAL)
                {
                    _fansStateList[funId].StateCode = AbnormalCode.SndFail;
                }
                else
                {
                    _fansStateList[funId].StateCode = AbnormalCode.None;
                }
                _fansStateList[funId].state = state;
                _fansStateList[funId].stateCount = 0;
                _fansStateList[funId].value = 0;

            }
        }
        /// <summary>
        /// 风扇转速判断是否稳定
        /// </summary>
        /// <returns></returns>
        private bool CheckFansStateStability()
        {
            foreach (var v in _fansStateList)
            {
                if (v.state != TempCtrState.STATE_ABNORMAL && v.state != TempCtrState.STATE_WORKING)
                {
                    return false;
                }
            }
            return true;
        }
        private bool CheckDutsTempStateStability()
        {
            foreach (var v in _dutTempStateList)
            {
                if (v.state != TempCtrState.STATE_ABNORMAL && v.state != TempCtrState.STATE_WORKING)
                {
                    return false;
                }
            }
            return true;
        }

        private void ClearDutsTempAbnormalState()
        {
            for (int i = 0; i < _dutTempStateList.Length; i++)
            {
                if (_dutTempStateList[i].state == TempCtrState.STATE_ABNORMAL)
                {
                    _dutTempStateList[i].StateCode = AbnormalCode.None;
                    _dutTempStateList[i].stateCount = 0;
                    // _dutTempStateList[i].value = 0;
                    _dutTempStateList[i].state = TempCtrState.STATE_PREPARE;
                }
            }
        }


        private bool OnCheckDutsTempStateStabilityTimeout()
        {
            for (int i = 0; i < _dutTempStateList.Length; i++)
            {
                if (_dutTempStateList[i].state != TempCtrState.STATE_ABNORMAL
                    && _dutTempStateList[i].state != TempCtrState.STATE_WORKING)
                {
                    _dutTempStateList[i].StateCode = AbnormalCode.WaitStabilityTimeout;
                    _dutTempStateList[i].stateCount = 0;
                    _dutTempStateList[i].state = TempCtrState.STATE_ABNORMAL;
                }
            }
            return true;
        }

        private void ChangeVolStage(bool isOn)
        {
            lock (_stageLock)
            {
                _setCBPwrIsOn = isOn;
                _cbPwrStage = VoltageStage.Adjusting;
            }
        }
    }
}
