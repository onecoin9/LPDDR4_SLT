using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Hsg.Common;
using Hsg.BLL.Net;
using Hsg.BLL.config;
using System.Threading;
using Hsg.BLL.ViewModel;
using static Hsg.BLL.DutMaster;
using Hsg.BLL.Service;

namespace Hsg.BLL.Model
{
    /// <summary>
    /// 用于内部沟通的事件
    /// </summary>
    public enum BSTEvent
    {
        //  EVT_INIT,
        /// <summary>
        /// 准备进入工作状态 ST_WORKING
        /// </summary>
        EVT_ENTRY_WORK_MODE,
        /// <summary>
        /// 退出准备状态回到 ST_PREPARE
        /// </summary>
        EVT_EXIT_WORK_MODE,
        /// <summary>
        /// 给测试板供电
        /// </summary>
        EVT_POWERUP_TB,
        /// <summary>
        /// 测试板联网后准备中
        /// </summary>
        EVT_GROUP_PREPARE,
        /// <summary>
        /// 测试板准备就绪
        /// </summary>
        EVT_GROUP_READY,
        /// <summary>
        /// 请求执行一个测试任务
        /// </summary>
        EVT_EXCUTE_TEST,
        /// <summary>
        /// 开始执行一个测试任务
        /// </summary>
        EVT_EXCUTE_START,
        /// <summary>
        /// 测试时间刷新
        /// </summary>
        EVT_TIME_UPDATE,
        /// <summary>
        /// 测试完成 失败或者成功
        /// </summary>
        EVT_FINISH,
        /// <summary>
        /// 测试超时
        /// </summary>
        EVT_TIMEOUT,
        /// <summary>
        /// 复测
        /// </summary>
        EVT_REPEAT_EXCUTE,
        /// <summary>
        /// 执行配方下一个阶段
        /// </summary>
        EVT_EXCUTE_NEXT_STAGE,
        /// <summary>
        /// 异常检查
        /// </summary>
        EVT_ABNORMAL_CHECK,
        /// <summary>
        /// 异常等待
        /// </summary>
        EVT_ABNORMAL_WAIT_TIMEOUT,
        /// <summary>
        /// 异常等待
        /// </summary>
        EVT_ABNORMAL_RETRY,
        /// <summary>
        /// 暂停报警等待计时
        /// </summary>
        EVT_PAUSE_ALARM_COUNTDOWN,
        /// <summary>
        /// 暂停报警等待计时
        /// </summary>
        EVT_RESUME_ALARM_COUNTDOWN,
        /// <summary>
        /// 取消测试任务
        /// </summary>
        EVT_CANCEL_TASK,
        /// <summary>
        /// 关闭程序
        /// </summary>
        EVT_DESTORY,
        /// <summary>
        /// 环境重试
        /// </summary>
        EVT_ENV_RETRY,
        /// <summary>
        /// 温度准备超时
        /// </summary>
        EVT_ENV_PREPARE_TIMEOUT,
        /// <summary>
        /// 温度准备就绪
        /// </summary>
        EVT_ENV_READY,
        /// <summary>
        /// 温度异常
        /// </summary>
        EVT_TEMP_BAD,
        /// <summary>
        /// 因为温度延迟执行
        /// </summary>
        EVT_EXEC_DELAY_FOR_TEMP,//
        /// <summary>
        /// 发现不是所有通讯板就绪，开启超时
        /// </summary>
        EVT_PREPARE_CHECK_TIMEOUT,//
    }

    /// <summary>
    /// 通讯板的状态
    /// </summary>
    public enum BSTState
    {
        /// <summary>
        ///初始化状态
        /// </summary>
        ST_INIT,
        /// <summary>
        /// 继续检测扫描失败的IP
        /// </summary>
        ST_PREPARE,
        ///// <summary>
        ///// 已经在线，等待开始测试
        ///// </summary>
        //ST_ONLINE,
        /// <summary>
        /// 进入等待状态，等待开始测试
        /// </summary>
        ST_READY,
        /// <summary>
        /// 进入工作状态，先检查通讯板状态和信息，再等待开始测试命令
        /// </summary>
        ST_WORKING,
        /// <summary>
        /// 测试结束，上报结果，重新进入 ST_WORKING 等待开始的命令
        /// </summary>
        ST_WORKE_END,
        /// <summary>
        /// 退出服务
        /// </summary>
        ST_DESTORY,
    }
    public delegate void IOnBSTeamStageChange(int teamId, TestStage stage);
    public delegate UdpServer IOnGetDutConn(int dutId);
    struct DutPostEventAsync
    {
        public int instanceId;
        public DutEvent_E evt;
        public bool valid;
    }
    public partial class BSTeam : StateMechine<BSTState, BSTEvent>
    {
        private ITeamViewModel _viewModel;
        private int _instanceId;
        private IOnBSTeamStageChange _onStageChange;
        private BSTeamConfig _bsTeamConfig;
        private TimerTask _timerTask;
        private int _retryTimerId = TimerTask.INVALID_TIMER_ID;// 任务重试
        private BSTEvent _retryEvent;
        private int _retryCount;// 重试计数
        private DateTime _startTime;// 开始测试的时间 
        private DateTime _alarmStartTime;// 警告发生倒计时
        //private TimeSpan _alarmPassTime;
        private int _counterTimerId = TimerTask.INVALID_TIMER_ID;// 计时器
        private int _alarmTimerId = TimerTask.INVALID_TIMER_ID;// 计时器
        private TestStage _lastState;
        private List<DutsManager> _dutsManagerList;
        private readonly object _stateLock = new object();
        private TempCtrTeam _tempTeamCtr;
        // private bool _debugAutoRetry = false;// 调试模式自动重测
        private bool _execDelayForTemp = false;
        private bool _abnormalWait = false; // 异常等待
        private bool _abnormalPause = false; // 异常警告暂停
        private bool _abnormalRetry = false;
        private bool _taskFinish = false; // 
                                          //private bool _testIsRunning = false;
                                          // 测试配方
        private PolicyManager _policyManager;
        private PolicyMember _curPolicyMember;
        private bool _withCancelDelay = false;// 取消请求被延迟
        private UInt32[,] _groupRecordInstance;
        private UInt32[,] _dutsExcuteStageCount; // 执行了几个测试阶段
        private Int32[] _dutsLastPassStageIndex;// dut最近通过的阶段索引
        private DateTime[,] _groupStagesStartTime;// 每个通讯板每一段开始的时间
                                                  // private DateTime[,] _dutsStageDuration;//每个dut每一段的测试时间 
        private CSVRecord _csvRecord;
        private TempState _currentTempState;
        private bool _temperatureAdjust = false;// 由于测试中不同的环境要求，需要重新进入ready 等待新环境就绪
        private int _excutePolicyMemberIndex
        {
            get { return _viewModel.PolicyTestCurStage; }
            set { _viewModel.PolicyTestCurStage = value; }
        } // 当前执行的是第几个配方内容
        private TeamStateManager _dutsStateMgr;

        public BSTeam(int id, ITeamViewModel viewModel, IOnBSTeamStageChange onStageChange) : base("BSTeam" + (id + 1).ToString())
        {
            _viewModel = viewModel;
            _instanceId = id;
            _onStageChange = onStageChange;
            _counterTimerId = TimerTask.INVALID_TIMER_ID;
            _bsTeamConfig = new BSTeamConfig(id, null);
            _dutsManagerList = new List<DutsManager>();
            _currentTempState = TempState.TmpNormal;
            // 根据情况选择高/常温
            if (_bsTeamConfig.OpenTempMgr)
            {
                _tempTeamCtr = new HightTempCtrTeam(id, OnTempTeamCtrStateChange, OnTempDutCtrStateChange, OnTempDutCtrValueChange);
            }
            else
            {
                _tempTeamCtr = new NormalTempCtrTeam(id, OnTempTeamCtrStateChange, OnTempDutCtrStateChange, OnTempDutCtrValueChange);
            }
            // 记录文件
            _csvRecord = BSController.TestRecord.GetRecordObject();
            _groupRecordInstance = new UInt32[BSTeamConfig.GROUP_COUNT, BSTeamConfig.ITEM_DUT_NUM];
            for (int i = 0; i < BSTeamConfig.GROUP_COUNT; i++)
            {
                for (int j = 0; j < BSTeamConfig.ITEM_DUT_NUM; j++)
                {
                    _groupRecordInstance[i, j] = _csvRecord.StartOneRecord();
                }
            }
            _groupExcuteFlags = new bool[BSTeamConfig.GROUP_COUNT];
            _dutsErrorCode = new byte[BSTeamConfig.DUTS_COUNT];
            _stateCodes = new ushort[BSTeamConfig.DUTS_COUNT];
            _lastEnvTemp = new string[BSTeamConfig.DUTS_COUNT];

            _retryPassCount = new UInt32[BSTeamConfig.DUTS_COUNT];
            _retryFailCount = new UInt32[BSTeamConfig.DUTS_COUNT];
            _retryWithFail = new bool[BSTeamConfig.DUTS_COUNT];
            _dutsBinCode = new byte[BSTeamConfig.DUTS_COUNT];
            //    _retryDutsManagerFlag = new bool[BSTeamConfig.GROUP_COUNT, BSTeamConfig.ITEM_DUT_NUM];
            _dutExecuteFlag = new bool[BSTeamConfig.DUTS_COUNT];// 一维
            _dutsMangerExecuteFlag = new bool[BSTeamConfig.GROUP_COUNT, BSTeamConfig.ITEM_DUT_NUM];// 二维
            _dutsExcuteStageCount = new UInt32[BSTeamConfig.GROUP_COUNT, BSTeamConfig.ITEM_DUT_NUM];
            _dutsLastPassStageIndex = new Int32[BSTeamConfig.DUTS_COUNT];

            _policyManager = PolicyManager.Instance;
            _timerTask = TimerTask.GetTimerTaskInstance();
            _dutsStateMgr = TeamStateManager.GetInstance();
            RegisterActionHandle();
        }
        private void RegisterActionHandle()
        {
            //  RegisterStateHandle(BSTState.ST_INIT, BSTEvent.EVT_INIT, DoActionFirstInit);
            //RegisterStateHandle(BSTState.ST_INIT, BSTEvent.EVT_POWERUP_TB, DoActionPowerupTestBoard);
            RegisterStateHandle(BSTState.ST_INIT, BSTEvent.EVT_GROUP_PREPARE, DoActionPrepare);
            RegisterStateHandle(BSTState.ST_INIT, BSTEvent.EVT_ENV_RETRY, DoActionEnvironmentRetry);
            RegisterStateHandle(BSTState.ST_INIT, BSTEvent.EVT_ENV_READY, DoActionInitTempReady);
            RegisterStateHandle(BSTState.ST_INIT, BSTEvent.EVT_DESTORY, DoActionDestory);

            //     RegisterStateHandle(BSTState.ST_PREPARE, BSTEvent.EVT_INIT, DoActionPrepareInit);
            RegisterStateHandle(BSTState.ST_PREPARE, BSTEvent.EVT_ENV_RETRY, DoActionEnvironmentRetry);
            RegisterStateHandle(BSTState.ST_PREPARE, BSTEvent.EVT_ENV_READY, DoActionTempReady);
            RegisterStateHandle(BSTState.ST_PREPARE, BSTEvent.EVT_ENV_PREPARE_TIMEOUT, DoActionTempPrepareTimeout);

            RegisterStateHandle(BSTState.ST_PREPARE, BSTEvent.EVT_PREPARE_CHECK_TIMEOUT, DoActionPrepareWaitTimeout);
            RegisterStateHandle(BSTState.ST_PREPARE, BSTEvent.EVT_GROUP_READY, DoActionGroupReady);
            RegisterStateHandle(BSTState.ST_PREPARE, BSTEvent.EVT_DESTORY, DoActionDestory);

            // RegisterStateHandle(BSTState.ST_READY, BSTEvent.EVT_INIT, DoActionTeamReadyInit);
            RegisterStateHandle(BSTState.ST_READY, BSTEvent.EVT_EXCUTE_TEST, DoActionExcuteTestPrepare);
            RegisterStateHandle(BSTState.ST_READY, BSTEvent.EVT_DESTORY, DoActionDestory);
            RegisterStateHandle(BSTState.ST_READY, BSTEvent.EVT_ENV_RETRY, DoActionEnvironmentRetry);
            RegisterStateHandle(BSTState.ST_READY, BSTEvent.EVT_EXCUTE_START, DoActionStartWork);
            RegisterStateHandle(BSTState.ST_READY, BSTEvent.EVT_EXEC_DELAY_FOR_TEMP, DoActionDelayExecTestReqForTemp);
            RegisterStateHandle(BSTState.ST_READY, BSTEvent.EVT_ENV_READY, DoActionTempReadyInWorking);
            RegisterStateHandle(BSTState.ST_READY, BSTEvent.EVT_TEMP_BAD, DoActionTempBadInWorking);

            RegisterStateHandle(BSTState.ST_WORKING, BSTEvent.EVT_TIMEOUT, DoActionTimeout);
            RegisterStateHandle(BSTState.ST_WORKING, BSTEvent.EVT_FINISH, DoActionTestFinish);
            RegisterStateHandle(BSTState.ST_WORKING, BSTEvent.EVT_CANCEL_TASK, DoActionCancelTestWork);

            RegisterStateHandle(BSTState.ST_WORKING, BSTEvent.EVT_ABNORMAL_CHECK, DoActionCheckAbnormalCheck);
            RegisterStateHandle(BSTState.ST_WORKING, BSTEvent.EVT_ABNORMAL_WAIT_TIMEOUT, DoActionAbnormalWait);
            RegisterStateHandle(BSTState.ST_WORKING, BSTEvent.EVT_PAUSE_ALARM_COUNTDOWN, DoActionPauseAlarmCountdown);
            RegisterStateHandle(BSTState.ST_WORKING, BSTEvent.EVT_RESUME_ALARM_COUNTDOWN, DoActionResumeAlarmCountdown);
            RegisterStateHandle(BSTState.ST_WORKING, BSTEvent.EVT_ABNORMAL_RETRY, DoActionAbnormalRetry);
            RegisterStateHandle(BSTState.ST_WORKING, BSTEvent.EVT_REPEAT_EXCUTE, DoActionRepeatExcute);
            RegisterStateHandle(BSTState.ST_WORKING, BSTEvent.EVT_EXCUTE_NEXT_STAGE, DoActionNextStageExcute);
            RegisterStateHandle(BSTState.ST_WORKING, BSTEvent.EVT_DESTORY, DoActionDestory);

            RegisterStateHandle(BSTState.ST_WORKE_END, BSTEvent.EVT_EXCUTE_TEST, DoActionExcuteTestForTestEnd);
            RegisterStateHandle(BSTState.ST_WORKE_END, BSTEvent.EVT_CANCEL_TASK, DoActionCancelWhenFinish);
            RegisterStateHandle(BSTState.ST_WORKE_END, BSTEvent.EVT_DESTORY, DoActionDestory);
            RegisterStateHandle(BSTState.ST_WORKE_END, BSTEvent.EVT_ENV_RETRY, DoActionEnvironmentRetry);
        }
        protected override void NotifyStateChange(BSTState state)
        {
            switch (state)
            {
                case BSTState.ST_INIT:
                    Stage = TestStage.ST_NOT_START;
                    DoFirstStateInit();
                    break;
                case BSTState.ST_PREPARE:
                    Stage = TestStage.ST_PREPARE;
                    DoActionPrepareStateInit();
                    break;
                case BSTState.ST_WORKE_END:
                    DoWorkEndStateInit();
                    Stage = _lastState;
                    break;
                case BSTState.ST_READY:
                    Stage = TestStage.ST_READY;
                    DoTeamReadyStateInit();
                    break;
                case BSTState.ST_WORKING:
                    Stage = TestStage.ST_TESTING;
                    DoStartWorkInit();
                    break;

            }

        }
        #region do state init
        private void DoFirstStateInit()
        {
            //   Hlog.E("DoActionFirstInit @@@@");
            int groupId = 0;
            for (int i = 0; i < SysConfig.TEAM_GROUP_NUM; i++)
            {
                DutsManager dm = new DutsManager(_instanceId, groupId, _tempTeamCtr, _viewModel, SysConfig.PORT_NUM, IOnDutsManagerStageChange);
                groupId++;
                _dutsManagerList.Add(dm);
                dm.BindUIUpdate(AppendLogToUi);
                dm.Run();
            }
            _tempTeamCtr.Run();
            if (_bsTeamConfig.TempCtrInitAllEnable)
            {
                _tempTeamCtr.StartWork();
            }
            _abnormalWait = false;
            _abnormalPause = false;
            _abnormalRetry = false;
            _taskFinish = false;
            _viewModel.AlarmMsg = "";
            _viewModel.AlarmFlag = false;
            AppendLogToDetil("等待设备就绪", LOG_TYPE.INFO);
            //Task.Delay(1000).Wait();
            //SetTBVoltageOnOff(true); // 
        }

        private void DoActionPrepareStateInit()
        {
            StopRetryTimer();
            // 只有异常状态或者初始状态支持 启动/重启 温控
            if (!_tempTeamCtr.CheckEnvIsReady())
            {
                _tempTeamCtr.StartWork();
                StartRetryTimer(_bsTeamConfig.GetEnvTempWaitTimeout(TempState.TmpHight) * 1000, BSTEvent.EVT_ENV_PREPARE_TIMEOUT);// 初始 选择 使用高温等待超时，避免等待太久。后续根据需要可以调整
            }
        }

        private void DoTeamReadyStateInit()
        {
            AppendLogToDetil($"进入Ready状态", LOG_TYPE.DONE);
            _execDelayForTemp = false;
            StopTimeCounter();
            StopRetryTimer();
            if (!_bsTeamConfig.IdlePowerHold && !_temperatureAdjust)// 环境切换或者 需要保持上电时不关闭
            {
                SetTBVoltageOnOff(false);// 检查完成可以关闭5V 等待测试
                Task.Delay(1000).Wait();
            }
        }
        private void DoStartWorkInit()// 某一个阶段的开始
        {
            int execSpan = 0;
            _startTime = DateTime.Now;
            _lastState = TestStage.ST_READY;
            _temperatureAdjust = false;
            _excuteCount = 1;
            StartTimeCounter();
            _execDelayForTemp = false;
            _taskExecLock = false;// 解除任务锁定
            ClearLogToDetail();// 清除历史记录

            _excutePolicyMemberIndex++;
            _curPolicyMember = _policyManager.GetPolicyMember(_excutePolicyMemberIndex);
            AppendLogToDetil($"开始载入方案内容{_excutePolicyMemberIndex + 1}", LOG_TYPE.INFO);
            if (_curPolicyMember == null) // 正常情况该逻辑不存在
            {
                AppendLogToDetil($"载入方案内容{_excutePolicyMemberIndex + 1} 失败", LOG_TYPE.ERROR);
                AppendLogToUi($"载入方案内容{_excutePolicyMemberIndex + 1} 失败", LOG_TYPE.ERROR);
                _viewModel.PolicyTestTotalStage = 0;
                _excutePolicyMemberIndex = -1;
                _bsTeamConfig.Timeout = 0;
                _bsTeamConfig.RetryMaxFailCount = 0;
                _bsTeamConfig.RetryResultOptimization = false;
                _bsTeamConfig.ExcuteFrequency = 0;
            }
            else
            {
                _viewModel.PolicyTestTotalStage = _policyManager.Policy.MemberList.Count;
                AppendLogToDetil($"配置名:{_curPolicyMember.param.CfgFileName}", LOG_TYPE.ERROR);
                AppendLogToDetil($"超时:{_curPolicyMember.param.TimeoutMinute} Min", LOG_TYPE.ERROR);
                AppendLogToDetil($"温度:{(_curPolicyMember.param.TempFlag == (byte)TempState.TmpHight ? "高温" : "室温")}", LOG_TYPE.ERROR);
                AppendLogToDetil($"Excute: {_curPolicyMember.param.ExcuteFrequency}/{_curPolicyMember.param.RepeatMaxFail} 优化:{_curPolicyMember.param.RepeatOptimization}", LOG_TYPE.ERROR);
                _bsTeamConfig.Timeout = (int)_curPolicyMember.param.TimeoutMinute;
                _bsTeamConfig.RetryMaxFailCount = (int)_curPolicyMember.param.RepeatMaxFail;
                _bsTeamConfig.ExcuteFrequency = _curPolicyMember.param.ExcuteFrequency;
                _bsTeamConfig.RetryResultOptimization = _curPolicyMember.param.RepeatOptimization;
            }
            AppendLogToUi($"开始第{_excutePolicyMemberIndex + 1}段 第{_excuteCount}次测试", LOG_TYPE.WARNNING);
            AppendLogToDetil($"开始第{_excutePolicyMemberIndex + 1}段 第{_excuteCount}次测试", LOG_TYPE.WARNNING);

            SetTBVoltageOnOff(true);

            for (int i = 0; i < BSTeamConfig.GROUP_COUNT; i++)
            {
                string stageInfo = $"[{_policyManager.Policy.MemberList.Count}-{_excutePolicyMemberIndex + 1}]";
                if (_groupExcuteFlags[i])
                {
                    bool[] execFlag = new bool[BSTeamConfig.ITEM_DUT_NUM];
                    for (int j = 0; j < BSTeamConfig.ITEM_DUT_NUM; j++)
                    {
                        execFlag[j] = _dutsMangerExecuteFlag[i, j];
                    }
                    _groupStagesStartTime[i, _excutePolicyMemberIndex] = DateTime.Now + TimeSpan.FromMilliseconds(execSpan);// 记录通讯板每一段开始的时间
                    _dutsManagerList[i].ExcuteTestTask(execFlag, _policyManager.LoadTestConfig(_excutePolicyMemberIndex), execSpan, _excuteCount.ToString(), stageInfo, _taskSerialNo);
                    execSpan += _bsTeamConfig.TeamExecSpanTime;
                }
            }

            //AppendLogToDetil("开始执行测试组任务", LOG_TYPE.INFO);
            //AppendLogToUi("开始执行测试", LOG_TYPE.INFO);
        }
        private void DoWorkEndStateInit()
        {
            _abnormalWait = false;
            _abnormalPause = false;
            _abnormalRetry = false;
            _temperatureAdjust = false;
            _viewModel.AlarmMsg = "";
            _viewModel.AlarmFlag = false;
            _taskFinish = false;
            _withCancelDelay = false;
            StopTimeCounter();
            SaveLastTestResult();
            StageFaileDutStatistics();
            _dutsStateMgr.UpdateDutsStateCode(_instanceId, _stateCodes, _lastEnvTemp);
            _tempTeamCtr.ExitTestMode();// 测试完成重新刷新故障温度板状态
            if (!_bsTeamConfig.IdlePowerHold)
            {
                SetTBVoltageOnOff(false);
            }
            // 同步状态到 dut
            for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++)
            {
                int groupId = 0;
                int id = 0;
                DutsLogicalMap.ConventUIdToGroupDutId(i, ref groupId, ref id);
                if (_dutsErrorCode[i] == DutMaster.ERR_CODE_OK)
                {
                    _dutsManagerList[groupId].SyncLastStatus(TestStage.ST_TEST_SUCCESS, id);
                }
                else if (_dutsErrorCode[i] != DutMaster.ERR_CODE_INALID)
                {
                    if (_dutsErrorCode[i] == DutMaster.ERR_CODE_FAIL1
                        || _dutsErrorCode[i] == DutMaster.ERR_CODE_FAIL2
                        )
                    {
                        _dutsManagerList[groupId].SyncLastStatus(TestStage.ST_TEST_FAIL, id);
                    }
                    else
                    {
                        _dutsManagerList[groupId].SyncLastStatus(TestStage.ST_TEST_TIMEOUT, id);
                    }
                }
            }
        }
        #endregion
        #region do event action

        private BSTState DoActionInitTempReady(object param)
        {
            if (_tempTeamCtr.CheckEnvIsReady()) // 需要再次确认
            {
                AppendLogToDetil($"初始温控就绪:" + _tempTeamCtr.GetVoltageInfor(), LOG_TYPE.DONE);
            }

            // 检查 通讯板是否就绪
            return BSTState.ST_INIT;
        }
        private void SetTBVoltageOnOff(bool isOn)
        {
            bool ret = _tempTeamCtr.Set5VSwitchOnOff(isOn);
            if (!ret)
            {
                Hlog.W(Mod, $"Set5VSwitchOnOff {isOn} failed");
                if (isOn)
                {
                    AppendLogToUi($"启动供电失败", LOG_TYPE.ERROR);
                }
                else
                {
                    AppendLogToUi($"关闭供电失败", LOG_TYPE.ERROR);
                }
            }
        }

        //private BSTState DoActionPowerupTestBoard(object param)
        //{
        //    SetTBVoltageOnOff(true);
        //    return BSTState.ST_INIT;
        //}
        private BSTState DoActionPrepare(object param)
        {
            int groupId = (int)param;
            Hlog.I(Mod, "Group Prepare:" + groupId);
            AppendLogToDetil($"发现板卡{groupId}", LOG_TYPE.INFO);
            //AppendLogToUi($"发现板卡{groupId} ", LOG_TYPE.DONE);
            return BSTState.ST_PREPARE;
        }



        private BSTState DoActionEnvironmentRetry(object param)
        {
            ClearLogToDetail();
            AppendLogToDetil($"开始重置测试环境", LOG_TYPE.DONE);
            StopRetryTimer();
            SetTBVoltageOnOff(false);// 先断电，3S
                                     // 重置状态
            for (int i = 0; i < _dutsManagerList.Count; i++)
            {
                _dutsManagerList[i].ResetStatus();
            }
            Task.Delay(3000).Wait();
            _tempTeamCtr.RsetEnvironment();// 重置初始状态
            Task.Delay(500).Wait();
            if (CurState == BSTState.ST_PREPARE)
            {
                DoActionPrepareStateInit();
            }
            //SetTBVoltageOnOff(true);
            return BSTState.ST_PREPARE;
        }
        private BSTState DoActionTempReady(object param)
        {
            bool checkHadReady = false;
            bool checkNotReady = false;
            if (!_tempTeamCtr.CheckEnvIsReady()) // 需要再次确认
            {
                return BSTState.ST_PREPARE;
            }
            StopRetryTimer();
            AppendLogToDetil($"温控就绪:" + _tempTeamCtr.GetVoltageInfor(), LOG_TYPE.DONE);
            // 检查 通讯板是否就绪
            foreach (var v in _dutsManagerList)
            {
                if (v.TestStage < TestStage.ST_READY)// 存在未就绪的再等10S
                {
                    //
                    if (!checkNotReady)
                    {
                        checkNotReady = true;
                    }
                }
                else
                {
                    checkHadReady = true;
                }
            }
            // 存在非就绪的 ，如果存在部分就绪就超时等待，否则继续等待
            if (checkNotReady)
            {
                if (checkHadReady)
                {
                    StartRetryTimer(10000, BSTEvent.EVT_PREPARE_CHECK_TIMEOUT);
                }
                return BSTState.ST_PREPARE;
            }
            return BSTState.ST_READY;
        }
        private BSTState DoActionTempPrepareTimeout(object param)
        {
            // _bsTeamConfig.TeamTempPrepareSecond*
            _tempTeamCtr.WaitTempStabilityTimeout();
            return BSTState.ST_PREPARE;
        }

        private BSTState DoActionPrepareWaitTimeout(object param)
        {
            return BSTState.ST_READY;
        }
        private BSTState DoActionGroupReady(object param)
        {
            int groupId = (int)param;
            Hlog.I(Mod, "Group ready:" + groupId);
            //AppendLogToUi($"板卡{groupId} 准备就绪", LOG_TYPE.DONE);
            //

            if (!_tempTeamCtr.CheckEnvIsReady())
            {
                AppendLogToDetil($"板卡{groupId}就绪 等待测试环境就绪", LOG_TYPE.DONE);
                // 等待温度就绪
                return BSTState.ST_PREPARE;
            }
            AppendLogToDetil($"板卡{groupId} 准备就绪", LOG_TYPE.DONE);
            // 调试模式 允许部分就绪使用
            foreach (var v in _dutsManagerList)
            {
                if (v.TestStage < TestStage.ST_READY) // 如果另外一个板未就绪，先等待10s.
                {
                    StopRetryTimer();
                    StartRetryTimer(10000, BSTEvent.EVT_PREPARE_CHECK_TIMEOUT);
                    return BSTState.ST_PREPARE;
                }
            }
            return BSTState.ST_READY;
        }


        private BSTState DoActionRepeatExcute(object param)
        {
            int execSpan = 0;
            _startTime = DateTime.Now;
            _lastState = TestStage.ST_READY;
            _taskFinish = false;//需要清除结束标志
            _excuteCount++;
            StartTimeCounter();
            ClearLogToDetail();// 清除历史记录
            //int groupId = 0;
            //int id = 0;
            //for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++)
            //{
            //    _stateCodes[i] = StateCode.SCODE_INVALID;
            //}

            AppendLogToUi($"开始第{_excutePolicyMemberIndex + 1}段 第{_excuteCount}次测试", LOG_TYPE.WARNNING);
            AppendLogToDetil($"开始第{_excutePolicyMemberIndex + 1}段 第{_excuteCount}次测试", LOG_TYPE.WARNNING);
            SetTBVoltageOnOff(true);
            for (int i = 0; i < BSTeamConfig.GROUP_COUNT; i++)
            {
                string stageInfo = $"[{_policyManager.Policy.MemberList.Count}-{_excutePolicyMemberIndex + 1}]";
                if (_groupExcuteFlags[i])
                {
                    bool[] execFlag = new bool[BSTeamConfig.ITEM_DUT_NUM];
                    for (int j = 0; j < BSTeamConfig.ITEM_DUT_NUM; j++)
                    {
                        execFlag[j] = _dutsMangerExecuteFlag[i, j];
                    }
                    _dutsManagerList[i].ExcuteTestTask(execFlag, _policyManager.LoadTestConfig(_excutePolicyMemberIndex), execSpan, _excuteCount.ToString(), stageInfo, _taskSerialNo);
                    if (_bsTeamConfig.DiagnosticMode)
                    {
                        _dutsManagerList[i].CommunicateBoardRebootCheck();
                    }
                    execSpan += _bsTeamConfig.TeamExecSpanTime;
                }
            }
            return BSTState.ST_WORKING;
        }
        private BSTState DoActionNextStageExcute(object param)
        {
            // 重置 重测计数
            _excuteCount = 0;
            _taskFinish = false;
            for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++)
            {
                if (_dutsErrorCode[i] == DutMaster.ERR_CODE_OK) // 把后续需要执行的dut状态重置
                {
                    _retryPassCount[i] = 0;
                    _retryFailCount[i] = 0;
                    _retryWithFail[i] = false;
                }
            }
            PolicyMember nextPolicy = _policyManager.GetPolicyMember(_excutePolicyMemberIndex + 1);
            if (_currentTempState != (TempState)nextPolicy.param.TempFlag)// check enviroment change.
            {
                AppendLogToUi($"测试环境变化，进入环境切换", LOG_TYPE.WARNNING);
                _tempTeamCtr.ExitTestMode();
                _temperatureAdjust = true;
                PostEventAsync(BSTEvent.EVT_EXCUTE_TEST, _excutePolicyMemberIndex + 1); // goto next stage 
                return BSTState.ST_READY;
            }
            DoStartWorkInit();
            return BSTState.ST_WORKING;
        }
        private BSTState DoActionCancelTestWork(object param)
        {
            if (_execDelayForTemp)// 正在等待温控
            {
                AppendLogToUi($"取消失败，必须等待温度检查完成", LOG_TYPE.WARNNING);
                return BSTState.ST_WORKING;
            }
            if (_abnormalWait)
            {
                AppendLogToUi($"异常处理中，不支持取消，需等待异常超时", LOG_TYPE.WARNNING);
                return BSTState.ST_WORKING;
            }
            AppendLogToUi($"取消测试任务", LOG_TYPE.WARNNING);
            StopTimeCounter();
            StopRetryTimer();

            if (_taskFinish)// 多线程可能在结束的时候，状态还没改变时收到取消请求（下一个任务还没开始的时候，如上一次复测完成，下一次未执行）
            {
                if (_excuteCount < _bsTeamConfig.ExcuteFrequency || _excutePolicyMemberIndex + 1 < _policyManager.Policy.MemberList.Count) // 没有执行完成 
                {
                    for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++)
                    {
                        if (_dutsErrorCode[i] == DutMaster.ERR_CODE_OK)
                        {
                            _dutsErrorCode[i] = DutMaster.ERR_CODE_CANCEL;
                        }
                    }
                }
                return BSTState.ST_WORKE_END;
            }
            _withCancelDelay = true;

            for (int i = 0; i < _dutsManagerList.Count; i++)
            {
                if (_groupExcuteFlags[i])
                {
                    _dutsManagerList[i].CancelWorkMode();
                }
            }
            return BSTState.ST_WORKING;
        }

        private BSTState DoActionTimeout(object param)
        {
            for (int i = 0; i < _dutsManagerList.Count; i++)
            {
                if (_groupExcuteFlags[i])
                {
                    _dutsManagerList[i].ExcuteTimeout();
                }
            }
            return BSTState.ST_WORKING;
        }
        private BSTState DoActionTimeCheck()
        {
            TimeSpan tSpan = DateTime.Now - _startTime;
            _viewModel.TimeCount = Tools.TimeSpanToString(tSpan);
            if (CurState == BSTState.ST_WORKING)
            {
                if (tSpan.TotalMinutes > _bsTeamConfig.Timeout)
                {
                    PostEventAsync(BSTEvent.EVT_TIMEOUT);
                    StopTimeCounter();
                }
            }
            return BSTState.ST_WORKING;
        }
        private BSTState DoActionTimeUpdate(object param)
        {
            TimeSpan tSpan = DateTime.Now - _startTime;
            _viewModel.TimeCount = Tools.TimeSpanToString(tSpan);
            return CurState;
        }

        private BSTState DoActionExcuteTestPrepare(object param)
        {
            _taskFinish = false;//需要清除结束标志
            _excuteCount = 0;
            // 收到测试请求，开始上电。
            if (param != null)
            {
                int policyStartIndex = Int32.Parse(param.ToString());
                _excutePolicyMemberIndex = policyStartIndex - 1;
                if (_excutePolicyMemberIndex < -1 || _excutePolicyMemberIndex >= _policyManager.Policy.MemberList.Count)
                {
                    _excutePolicyMemberIndex = -1;
                }
            }
            else // 数次执行需要重置信息
            {
                _excutePolicyMemberIndex = -1;
                _taskSerialNo = string.Format($"{Tools.GetTimestampToSecond()}-{_instanceId + 1}");
                // _testStartTime = DateTime.Now;
                for (int i = 0; i < _dutsLastPassStageIndex.Length; i++)
                {
                    _dutsLastPassStageIndex[i] = -1;
                }
                _groupStagesStartTime = new DateTime[BSTeamConfig.GROUP_COUNT, _policyManager.Policy.MemberList.Count];// 重新赋值
                                                                                                                       // _dutsStageDuration = new DateTime[BSTeamConfig.DUTS_COUNT, _policyManager.Policy.MemberList.Count];// 重新赋值
            }
            _viewModel.PolicyTestTotalStage = _policyManager.Policy.MemberList.Count;
            StopRetryTimer();
            // 上电
            SetTBVoltageOnOff(true);
            if (_policyManager.Policy.TempFlag == (uint)TempState.TmpHight // 只有加热模式或者混合模式需要去控制dut 温度是否起来
                || _policyManager.Policy.TempFlag == (uint)TempState.TmpMixture)
            {
                Hlog.I(MOD_ID, "init sync duts temp flags");
                if (_policyManager.Policy.MemberList[_excutePolicyMemberIndex + 1].param.TempFlag == (byte)TempState.TmpHight)
                {
                    _tempTeamCtr.SyncDutsEnableState(_dutExecuteFlag);//// 部分关闭
                    _currentTempState = TempState.TmpHight;
                }
                else
                {
                    bool[] disableFlag = new bool[_dutExecuteFlag.Length];
                    _tempTeamCtr.SyncDutsEnableState(disableFlag);// 全部关闭
                    _currentTempState = TempState.TmpNormal;
                }
            }

            if (!_tempTeamCtr.CheckEnvIsReady() && !_execDelayForTemp)
            {
                _execDelayForTemp = true;
                AppendLogToUi($"测试环境未就绪延迟等待执行", LOG_TYPE.WARNNING);
                AppendLogToDetil("测试环境未就绪延迟等待执行", LOG_TYPE.INFO);
                _tempTeamCtr.StartWork();
                StartRetryTimer(_bsTeamConfig.GetEnvTempWaitTimeout(_currentTempState) * 1000, BSTEvent.EVT_EXEC_DELAY_FOR_TEMP);
                return BSTState.ST_READY;
            }
            // 上电后3秒开始执行
            StartRetryTimer(3000, BSTEvent.EVT_EXCUTE_START);
            return BSTState.ST_READY;
        }

        private BSTState DoActionStartWork(object param)
        {
            // 重置状态
            for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++)
            {
                _retryPassCount[i] = 0;
                _retryFailCount[i] = 0;
                _retryWithFail[i] = false;
            }
            StopRetryTimer();
            _tempTeamCtr.EntryTestMode(); // 进入测试模式，锁定异常值
            return BSTState.ST_WORKING;
        }


        private BSTState DoActionTempReadyInWorking(object param)
        {
            if (!_tempTeamCtr.CheckEnvIsReady())// 再次确认
            {
                return BSTState.ST_READY;
            }
            if (_execDelayForTemp)
            {
                StopRetryTimer();
                // 温度就绪开始执行
                return DoActionStartWork(null);
            }
            return BSTState.ST_READY;
        }
        private BSTState DoActionTempBadInWorking(object param)
        {
            if (_execDelayForTemp)
            {
                StopRetryTimer();
                //温度失败开始执行
                PostEventAsync(BSTEvent.EVT_EXCUTE_START);
            }
            return BSTState.ST_READY;
        }
        private BSTState DoActionDelayExecTestReqForTemp(object param)
        {
            _tempTeamCtr.WaitTempStabilityTimeout();
            Task.Delay(1000).Wait(); // 等待状态同步
            PostEventAsync(BSTEvent.EVT_EXCUTE_START);
            return BSTState.ST_READY;
        }
        private BSTState DoActionTestFinish(object param)
        {
            _taskFinish = true;
            StopTimeCounter();

            if (_abnormalWait)  // 延迟结束，等待异常超时
            {
                if (_abnormalRetry)
                {
                    AppendLogToDetil("测试结束，开始异常重试", LOG_TYPE.INFO);
                    return DoActionAbnormalRetry(null);
                }
                AppendLogToDetil("测试结束，等待异常处理中", LOG_TYPE.INFO);
                return BSTState.ST_WORKING;
            }

            // 记录异常状态
            for (int i = 0; i < _dutsManagerList.Count; i++)
            {
                if (!_groupExcuteFlags[i])
                {
                    continue;
                }
                byte[] errorCodes = _dutsManagerList[i].GetErrorCode();
                ushort[] stateCodes = _dutsManagerList[i].GetStateCode();
                string[] envTemps = _dutsManagerList[i].GetLastTempValue();
                bool hadComminucateTbError = false;// 记录是否有通信版异常
                for (int j = 0; j < BSTeamConfig.ITEM_DUT_NUM; j++)
                {
                    int uid = DutsLogicalMap.ConventIdToUI(j, i);
                    if (_dutsMangerExecuteFlag[i, j]) // 只更新执行的状态
                    {
                        _dutsErrorCode[uid] = errorCodes[j];
                        _stateCodes[uid] = stateCodes[j];
                        _lastEnvTemp[uid] = envTemps[j];
                        if (stateCodes[j] == StateCode.SCODE_TB_COMMUNICATE_ERROR)// 记录
                        {
                            hadComminucateTbError = true;
                        }
                    }
                }
                if (hadComminucateTbError)
                {
                    _dutsStateMgr.RecordCommunicateTBAbnormal(_instanceId, i);
                }
            }
            //

            AppendLogToDetil("本次测试结束:" + Tools.HexToString(_dutsErrorCode), LOG_TYPE.INFO);

            // 输出测试结果到日志
            int passCount = 0;
            int failCount = 0;
            int timeoutCount = 0;
            int otherCount = 0;
            string passDuts = "";
            string failDuts = "";
            string timeoutDuts = "";
            for (int d = 0; d < BSTeamConfig.DUTS_COUNT; d++)
            {
                if (!_dutExecuteFlag[d])
                    continue;
                int groupId = 0, id = 0;
                DutsLogicalMap.ConventUIdToGroupDutId(d, ref groupId, ref id);
                byte ec = _dutsErrorCode[d];
                ushort sc = _stateCodes[d];
                string dutName = $"Dut{d + 1}";
                if (ec == DutMaster.ERR_CODE_OK)
                {
                    passCount++;
                    passDuts += dutName + " ";
                }
                else if (ec == DutMaster.ERR_CODE_FAIL1 || ec == DutMaster.ERR_CODE_FAIL2)
                {
                    failCount++;
                    failDuts += $"{dutName}[0x{sc:X2}] ";
                }
                else if (ec == DutMaster.ERR_CODE_TIMEOUT)
                {
                    timeoutCount++;
                    timeoutDuts += $"{dutName}[0x{sc:X2}] ";
                }
                else
                {
                    otherCount++;
                }
            }
            string resultSummary = $"结果: PASS={passCount} FAIL={failCount} TIMEOUT={timeoutCount}";
            if (otherCount > 0)
                resultSummary += $" OTHER={otherCount}";
            AppendLogToUi(resultSummary, failCount > 0 ? LOG_TYPE.ERROR : LOG_TYPE.DONE);
            AppendLogToDetil(resultSummary, failCount > 0 ? LOG_TYPE.ERROR : LOG_TYPE.DONE);
            if (failDuts.Length > 0)
            {
                AppendLogToDetil("失败Dut:" + failDuts, LOG_TYPE.ERROR);
            }
            if (timeoutDuts.Length > 0)
            {
                AppendLogToDetil("超时Dut:" + timeoutDuts, LOG_TYPE.ERROR);
            }

            //加严复测模式(需要放在靠后位置)
            if (CheckRetryTest(_withCancelDelay))
            {
                //AppendLogToUi("继续复测开始", LOG_TYPE.WARNNING);
                if (_bsTeamConfig.RepeatIntervalSec > 0)
                {
                    StartRetryTimer((int)_bsTeamConfig.RepeatIntervalSec * 1000, BSTEvent.EVT_REPEAT_EXCUTE);
                }
                else
                {
                    PostEventAsync(BSTEvent.EVT_REPEAT_EXCUTE);
                }
                return BSTState.ST_WORKING;
            }

            //多阶段测试模式(需要放在最后位置)
            if (CheckPolicyNextStageTest(_withCancelDelay))
            {
                if (_bsTeamConfig.RepeatIntervalSec > 0)
                {
                    StartRetryTimer((int)_bsTeamConfig.RepeatIntervalSec * 1000, BSTEvent.EVT_EXCUTE_NEXT_STAGE);
                }
                else
                {
                    PostEventAsync(BSTEvent.EVT_EXCUTE_NEXT_STAGE);
                }
                return BSTState.ST_WORKING;
            }

            if (_withCancelDelay)
            {
                if (_excuteCount < _bsTeamConfig.ExcuteFrequency || _excutePolicyMemberIndex + 1 < _policyManager.Policy.MemberList.Count) // 没有执行完成 
                {
                    for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++)
                    {
                        if (_dutsErrorCode[i] == DutMaster.ERR_CODE_OK)
                        {
                            _dutsErrorCode[i] = DutMaster.ERR_CODE_CANCEL;
                        }
                    }
                }
            }

            return BSTState.ST_WORKE_END;
        }


        private BSTState DoActionCancelWhenFinish(object param)
        {
            AppendLogToUi($"取消测试任务", LOG_TYPE.WARNNING);
            StopRetryTimer();
            return BSTState.ST_WORKE_END;
        }

        private BSTState DoActionDestory(object param)
        {
            StopRetryTimer();
            for (int i = 0; i < _dutsManagerList.Count; i++)
            {
                _dutsManagerList[i].Destory();
            }
            _tempTeamCtr.Exit();
            return BSTState.ST_DESTORY;
        }

        private BSTState DoActionCheckAbnormalCheck(object param)
        {
            // StopRetryTimer();
            string alarmMsg = "";
            for (int i = 0; i < _dutsManagerList.Count; i++)
            {
                if (_dutsManagerList[i].AlarmState != AlarmType.None)
                {
                    if (alarmMsg.Length > 0)
                    {
                        alarmMsg += "\r\n";
                    }

                    if (_dutsManagerList[i].AlarmState == AlarmType.TCNet)
                    {
                        alarmMsg += "[板卡" + i.ToString() + "]" + _tempTeamCtr.GetStateInfo();
                        // 测试中的电压异常需要单独记录
                        if (!_tempTeamCtr.CheckVoltageIsReady())
                        {
                            string volInfo = "Vol:" + _tempTeamCtr.GetVoltageInfor();
                            _dutsStateMgr.UpdateTempCtrStateCode(_instanceId, StateCode.SCODE_TEMP_MAIN_ERROR, volInfo);
                        }
                        break;
                    }
                    string foundMsg = AlarmService.AlarmTypeToString(_dutsManagerList[i].AlarmState);
                    alarmMsg += "[板卡" + i.ToString() + "]" + foundMsg;
                    //AppendLogToUi("发现异常:" + alarmMsg, LOG_TYPE.ERROR);                    
                }
            }
            if (alarmMsg.Length > 0)
            {
                _viewModel.AlarmMsg = alarmMsg;
                _viewModel.AlarmFlag = true;
            }
            if (_viewModel.AlarmFlag)
            {
                // bool reported = false;
                // ** 注意上报内容不能带空格 影响handler 软件解析
                if (_workModeOpen)
                {
                    AlarmService.instance.SendAlarm(_instanceId, string.Format("测试异常(请工程人员介入处理)"));
                }
                AppendLogToUi("上报异常:" + _viewModel.AlarmMsg, LOG_TYPE.WARNNING);

            }
            return BSTState.ST_WORKING;
        }
        private BSTState DoActionAbnormalWait(object param)
        {
            if (_abnormalWait && !_abnormalPause)
            {
                _abnormalWait = false;
                AppendLogToUi("异常处理超时，退出等待", LOG_TYPE.WARNNING);
                // 清除报警重新测试
                _viewModel.AlarmMsg = "";
                _viewModel.AlarmFlag = false;
                if (_taskFinish) // 异常等待超时，需要注意，当某一个没有测试完，可以等待它完成。
                {
                    PostEventAsync(BSTEvent.EVT_FINISH);// 重新通知测试结束
                }
            }

            return BSTState.ST_WORKING;
        }

        private BSTState DoActionPauseAlarmCountdown(object param)
        {
            if (_abnormalWait)
            {
                StopAlarmTimeCounter();
                _abnormalPause = true;
                AppendLogToUi("暂停报警任务处理", LOG_TYPE.WARNNING);
            }

            return BSTState.ST_WORKING;
        }

        private BSTState DoActionResumeAlarmCountdown(object param)
        {
            if (_abnormalWait)
            {
                StartAlarmTimeCounter();
                _abnormalPause = false;
                AppendLogToUi("恢复报警任务处理", LOG_TYPE.WARNNING);
            }

            return BSTState.ST_WORKING;
        }

        private BSTState DoActionAbnormalRetry(object param)
        {
            StopRetryTimer();
            StopAlarmTimeCounter();
            StopTimeCounter();
            _viewModel.AlarmMsg = "";
            _viewModel.AlarmFlag = false;
            if (!_taskFinish)
            {
                for (int i = 0; i < _dutsManagerList.Count; i++)
                {
                    if (_groupExcuteFlags[i])
                    {
                        _dutsManagerList[i].CancelWorkMode();
                    }
                }
                AppendLogToUi("等待结束再自动重试", LOG_TYPE.WARNNING);
                _abnormalRetry = true;
                return BSTState.ST_WORKING;
            }

            _abnormalWait = false;
            _abnormalPause = false;
            _abnormalRetry = false;

            // 清除测试状态
            Array.Clear(_groupExcuteFlags, 0, BSTeamConfig.GROUP_COUNT);
            Array.Clear(_dutsErrorCode, 0, _dutsErrorCode.Length);
            Array.Clear(_stateCodes, 0, _stateCodes.Length);
            Array.Clear(_dutsExcuteStageCount, 0, _dutsExcuteStageCount.Length);

            for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++)
            {
                int groupId = 0;
                int id = 0;
                DutsLogicalMap.ConventUIdToGroupDutId(i, ref groupId, ref id);

                _dutsMangerExecuteFlag[groupId, id] = _dutExecuteFlag[i];
                if (_dutExecuteFlag[i])
                {
                    _groupExcuteFlags[groupId] = true;
                }
            }
            AppendLogToUi("收到任务请求", LOG_TYPE.WARNNING);
            // 清除所有dut的原来状态
            for (int i = 0; i < BSTeamConfig.GROUP_COUNT; i++)
            {
                _dutsManagerList[i].ResetAllDutsState();
            }

            AppendLogToUi("尝试重新执行", LOG_TYPE.WARNNING);
            PostEventAsync(BSTEvent.EVT_EXCUTE_TEST);// 从头开始执行
            return BSTState.ST_READY;
        }

        private BSTState DoActionExcuteTestForTestEnd(object param)
        {
            PostEventAsync(BSTEvent.EVT_EXCUTE_TEST);
            // 返回就绪状态，继续执行
            return BSTState.ST_READY;
        }
        #endregion

        #region time counter

        private void StartTimeCounter()
        {
            _counterTimerId = _timerTask.StartTimer(1000, true, TimeCounterTimeout);
            if (_counterTimerId == TimerTask.INVALID_TIMER_ID)
            {
                Hlog.E(Mod, "create time failed.");
            }
            Hlog.D(Mod, "StartTimeCounter:" + _counterTimerId);
        }
        private void TimeCounterTimeout(int timerId)
        {
            if (_counterTimerId == timerId)
            {
                DoActionTimeCheck();
            }
            else
            {
                Hlog.E(Mod, "invalid timerid for timecounter:" + timerId);
            }

        }
        private void StopTimeCounter()
        {
            if (_counterTimerId != TimerTask.INVALID_TIMER_ID)
            {
                _timerTask.StopTimer(ref _counterTimerId);
            }
            Hlog.D(Mod, "StopTimeCounter:" + _counterTimerId);
        }
        #endregion

        #region alarm time counter

        private void DoAlarmTimeCheck()
        {
            TimeSpan tSpan = DateTime.Now - _alarmStartTime;
            TimeSpan leftTime = TimeSpan.FromSeconds(_bsTeamConfig.AbnormalWaitSecond);
            if (tSpan.TotalSeconds >= _bsTeamConfig.AbnormalWaitSecond)
            {
                _viewModel.AlarmCountdown = "00:00:00";
                if (CurState == BSTState.ST_WORKING)
                {
                    StopAlarmTimeCounter();
                    PostEventAsync(BSTEvent.EVT_ABNORMAL_WAIT_TIMEOUT);
                }
            }
            else
            {
                _viewModel.AlarmCountdown = Tools.TimeSpanToString(leftTime - tSpan);
            }
        }
        private void StartAlarmTimeCounter()
        {
            //  TimeSpan targetTime  = DateTime.Now + TimeSpan.FromSeconds(_bsTeamConfig.TeamTempPrepareSecond);
            _alarmStartTime = DateTime.Now;
            _alarmTimerId = _timerTask.StartTimer(1000, true, AlarmTimeCounterTimeout);
            if (_alarmTimerId == TimerTask.INVALID_TIMER_ID)
            {
                Hlog.E(Mod, "create time failed.");
            }
            Hlog.D(Mod, "StartAlarmTimeCounter:" + _alarmTimerId);
        }
        private void AlarmTimeCounterTimeout(int timerId)
        {
            if (_alarmTimerId == timerId)
            {
                DoAlarmTimeCheck();
            }
            else
            {
                Hlog.E(Mod, "alarm invalid timerid for timecounter:" + timerId);
            }
        }
        private void StopAlarmTimeCounter()
        {
            Hlog.D(Mod, "StopAlarmTimeCounter:" + _alarmTimerId);
            if (_alarmTimerId != TimerTask.INVALID_TIMER_ID)
            {
                _timerTask.StopTimer(ref _alarmTimerId);
            }
        }
        #endregion
        #region timeout retry
        private void StartRetryTimer(int msecond, BSTEvent eventId)
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
            if (_retryTimerId == TimerTask.INVALID_TIMER_ID)
            {
                Hlog.E(Mod, "assign timer id failed");
            }
            Hlog.I(Mod, "start retry timer team:" + _retryTimerId + " time:" + msecond + " evtId:" + eventId);
        }
        private void StopRetryTimer()
        {
            if (_retryTimerId != TimerTask.INVALID_TIMER_ID)
            {
                Hlog.I(Mod, "stop retry timer team:" + _retryTimerId);
                _timerTask.StopTimer(ref _retryTimerId);
                _retryCount = 0;
            }
        }
        private void RetryActionTimeout(int timerId)
        {
            if (timerId == _retryTimerId)
            {
                Hlog.I(Mod, "retry action timeout team:" + _retryTimerId);
                _retryTimerId = TimerTask.INVALID_TIMER_ID;
                PostEventAsync(_retryEvent);
            }
        }

        #endregion
        void IOnDutsManagerStageChange(int teamId, int groupId, TestStage stage)
        {
            bool testFinish = false;
            TestStage nextStage = TestStage.ST_TEST_SUCCESS; // 用来寻找最后的状态，当
            Hlog.I(Mod, "DutsManagerStageChange:" + teamId + "-" + groupId + ":" + stage);
            lock (_stateLock)
            {
                switch (stage)
                {
                    case TestStage.ST_NOT_START:
                        break;
                    case TestStage.ST_PREPARE:
                        PostEventAsync(BSTEvent.EVT_GROUP_PREPARE, groupId);
                        break;
                    case TestStage.ST_READY:
                        PostEventAsync(BSTEvent.EVT_GROUP_READY, groupId);
                        break;
                    case TestStage.ST_TEST_FAIL:// 测试失败
                    case TestStage.ST_TEST_SUCCESS:// 测试成功
                    case TestStage.ST_TEST_TIMEOUT://测试超时
                        if (_dutsManagerList[groupId].AlarmState != AlarmType.None)
                        {
                            if (_bsTeamConfig.AbnormalWaitSecond > 0)// 小于等于0 时 不报警
                            {
                                PostEventAsync(BSTEvent.EVT_ABNORMAL_CHECK);// 启动异常检查
                                _abnormalWait = true;
                                if (!_abnormalPause)
                                {
                                    StopAlarmTimeCounter();
                                    StartAlarmTimeCounter();
                                    Hlog.I("start  StartAlarmTimeCounter");
                                }
                                //  StopRetryTimer();
                                //  StartRetryTimer(_bsTeamConfig.AbnormalWaitSecond * 1000, BSTEvent.EVT_ABNORMAL_WAIT); // 启的异常保护期
                            }
                        }
                        for (int i = 0; i < BSTeamConfig.GROUP_COUNT; i++)
                        {
                            if (_groupExcuteFlags[i])
                            {
                                if (_dutsManagerList[i].TestStage <= TestStage.ST_TESTING)
                                {
                                    testFinish = false;
                                    break;
                                }
                                else if (nextStage != TestStage.ST_TEST_TIMEOUT
                                   && nextStage != _dutsManagerList[i].TestStage
                                   && _dutsManagerList[i].TestStage != TestStage.ST_TEST_SUCCESS)
                                {
                                    nextStage = _dutsManagerList[i].TestStage;
                                }
                            }
                            testFinish = true;
                        }
                        break;
                }

                if (testFinish)
                {
                    if (_lastState != nextStage)// 避免重复上报
                    {
                        _lastState = nextStage; // 得到最后的状态，如果有超时则为超时，如果有失败则为失败。
                        Hlog.I(Mod, "BSTeam finish state:" + _lastState);
                        //  _taskFinish = true;
                        StopTimeCounter();
                        PostEventAsync(BSTEvent.EVT_FINISH);
                    }
                }
            }
        }
        void OnTempTeamCtrStateChange(TempCtrState state)
        {
            if (state == TempCtrState.STATE_WORKING)
            {
                if (_tempTeamCtr.CheckEnvIsReady())
                {
                    PostEventAsync(BSTEvent.EVT_ENV_READY);
                    _dutsStateMgr.UpdateTempCtrStateCode(_instanceId, StateCode.SCODE_OK);
                }
                else
                {
                    string info = _tempTeamCtr.GetVoltageInfor();
                    AppendLogToDetil($"等待电压就绪: " + info, LOG_TYPE.ERROR);
                }

            }
            else if (state == TempCtrState.STATE_ABNORMAL)
            {
                if (CurState == BSTState.ST_READY && _execDelayForTemp)
                {
                    PostEventAsync(BSTEvent.EVT_TEMP_BAD);
                }
                //string abnormalInfo = "";
                string abnormalInfo = _tempTeamCtr.GetStateInfo();
                switch (_tempTeamCtr.StateCode)
                {
                    case AbnormalCode.FanSpeed:
                        ushort[] speeds = new ushort[0];
                        _tempTeamCtr.GetFanSpeed(ref speeds);
                        AppendLogToDetil(abnormalInfo, LOG_TYPE.ERROR);
                        AppendLogToUi(abnormalInfo, LOG_TYPE.ERROR);
                        _dutsStateMgr.UpdateTempCtrStateCode(_instanceId, StateCode.SCODE_TEMP_FUN_ERROR, $"{speeds[0]},{speeds[1]},{speeds[2]},{speeds[3]}");
                        break;
                    case AbnormalCode.WaitStabilityTimeout://请求超时
                    case AbnormalCode.SndFail://请求失败
                        AppendLogToDetil(abnormalInfo, LOG_TYPE.ERROR);
                        AppendLogToUi(abnormalInfo, LOG_TYPE.ERROR);
                        _dutsStateMgr.UpdateTempCtrStateCode(_instanceId, StateCode.SCODE_TEMP_CONNECT_ERROR);
                        break;
                    case AbnormalCode.Voltage://电压不到位
                        string volInfo = "Vol:" + _tempTeamCtr.GetVoltageInfor();
                        AppendLogToDetil(abnormalInfo, LOG_TYPE.ERROR);
                        AppendLogToUi(abnormalInfo, LOG_TYPE.ERROR);
                        _dutsStateMgr.UpdateTempCtrStateCode(_instanceId, StateCode.SCODE_TEMP_MAIN_ERROR, volInfo);
                        break;
                }
            }
        }

        void OnTempDutCtrValueChange(int id, float value)
        {
            if (value > 0)
            {
                _viewModel.DutTemps[id] = (short)(value * 10);
            }
            else
            {
                _viewModel.DutTemps[id] = 0;
            }
        }
        void OnTempDutCtrStateChange(int id, TempCtrState state, float value)
        {

            if (state == TempCtrState.STATE_ABNORMAL && CurState == BSTState.ST_WORKING)
            {
                int groupId = 0;
                int subIndex = 0;
                if (DutsLogicalMap.ConventUIdToGroupDutId(id, ref groupId, ref subIndex))
                {
                    if (!_tempTeamCtr.CheckEnvIsReady())// 测试环境破坏
                    {
                        _dutsManagerList[groupId].ExcuteDutsTempBad(subIndex, value, true);
                    }
                    else
                    {
                        _dutsManagerList[groupId].ExcuteDutsTempBad(subIndex, value);
                    }
                }
            }
        }

        /// <summary>
        /// 加严复测检查
        /// </summary>
        /// <returns> 返回代表是否继续测试</returns>
        bool CheckRetryTest(bool withCancelTask)
        {
            /*
                if (!_bsTeamConfig.RepeatTest)
                {
                    return false;
                }
                if (_continueRetryTm == 0) // 首次复测记录所有要求复测的状况
                {
                    Buffer.BlockCopy(_dutsMangerExecuteFlag, 0, _retryDutsManagerFlag, 0, _dutsMangerExecuteFlag.GetLength(0) * _dutsMangerExecuteFlag.GetLength(1) * sizeof(bool));
                }
                _continueRetryTm++;
                //记录测试成功计数
                AppendLogToDetil($"完成第{_continueRetryTm}次测试", LOG_TYPE.WARNNING);
            */
            for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++)
            {
                int groupId = 0;
                int id = 0;
                DutsLogicalMap.ConventUIdToGroupDutId(i, ref groupId, ref id);
                if (!_dutExecuteFlag[i]) // 无任务不需要重试
                {
                    continue;
                }

                if (_dutsErrorCode[i] == DutMaster.ERR_CODE_OK)
                {
                    _retryPassCount[i]++;
                }
                else
                {
                    if (!_dutsMangerExecuteFlag[groupId, id]) // 已经记录了状态
                    {
                        continue;
                    }
                    if (!_retryWithFail[i]) //明显被测试板判断测试FAIL的添加对应标记
                    {
                        if (_dutsErrorCode[i] == DutMaster.ERR_CODE_FAIL1
                        || _dutsErrorCode[i] == DutMaster.ERR_CODE_FAIL2)
                        {
                            _retryWithFail[i] = true;
                        }
                    }
                    _retryFailCount[i]++;
                }

                // 判定需要结束测试的逻辑
                if ((_bsTeamConfig.RetryMaxFailCount > 0 && _retryFailCount[i] >= _bsTeamConfig.RetryMaxFailCount) // 超出最大失败
                    || _excuteCount >= _bsTeamConfig.ExcuteFrequency// 达到最大执行次数
                    || (_dutsErrorCode[i] != DutMaster.ERR_CODE_OK && _dutsManagerList[groupId].AlarmState != AlarmType.None)) // 存在异常预警，不继续执行
                {
                    _dutsMangerExecuteFlag[groupId, id] = false; // 移除测试任务
                    SaveStageTestDetail(groupId, id);// 结束本轮测试的单元需要保存测试信息
                }
            }
            bool hadGroupTask = false;
            for (int i = 0; i < BSTeamConfig.GROUP_COUNT; i++)
            {
                if (_groupExcuteFlags[i])
                {
                    bool foundTask = false;
                    _dutsManagerList[i].OnSaveDutsTestResult(_bsTeamConfig.ExcuteFrequency <= 1 ? true : false);// 只执行一次的任务，保留所有结果，需要复测的只保留失败的结果
                    for (int j = 0; j < BSTeamConfig.ITEM_DUT_NUM; j++)
                    {
                        if (_dutsMangerExecuteFlag[i, j])
                        {
                            foundTask = true;
                            break;
                        }
                    }
                    if (!foundTask) // 没有dut任务就取消通讯板任务
                    {
                        _groupExcuteFlags[i] = false;
                    }
                    else
                    {
                        hadGroupTask = true;
                    }
                }
            }

            if (_excuteCount < _bsTeamConfig.ExcuteFrequency
                && !withCancelTask
                && hadGroupTask)
            {

                return true;
            }
            // 测试完成
            if (_bsTeamConfig.ExcuteFrequency <= 1) // 只做一次测试，不需要对结果做优化或者二次判定
            {
                for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++) // 记录每个dut 最近pass 的stage index
                {
                    if (_dutExecuteFlag[i] && _dutsErrorCode[i] == DutMaster.ERR_CODE_OK)
                    {
                        _dutsLastPassStageIndex[i] = _excutePolicyMemberIndex;
                    }
                }
                return false;
            }
            for (int i = 0; i < _dutsErrorCode.Length; i++)
            {
                // 测试成功次数不达标都定义为失败
                if (!_dutExecuteFlag[i]) // 无任务不需要重试
                {
                    continue;
                }
                if (_dutsLastPassStageIndex[i] + 1 != _excutePolicyMemberIndex)// 判断dut 是否已经终结测试，已经终结的，不再对结果做重复判定
                {
                    continue;
                }
                if (_dutsErrorCode[i] != DutMaster.ERR_CODE_INALID && _retryPassCount[i] < _bsTeamConfig.ExcuteFrequency)
                {
                    if (_retryWithFail[i]) // 除非有被测试板明确判定为失败的，其他情况定为不确定的环境因素
                    {
                        _dutsErrorCode[i] = DutMaster.ERR_CODE_FAIL2;
                    }
                    else
                    {
                        if (_bsTeamConfig.RetryResultOptimization
                            && _retryPassCount[i] >= 1
                           && (_retryPassCount[i] + _retryFailCount[i]) >= _bsTeamConfig.ExcuteFrequency) // 
                        {
                            _dutsErrorCode[i] = DutMaster.ERR_CODE_OK;
                        }
                        else
                        {
                            _dutsErrorCode[i] = DutMaster.ERR_OTHER_ENV_BAD;
                        }
                    }
                }
                if (_dutsErrorCode[i] == DutMaster.ERR_CODE_OK) // 记录每个dut 最近pass 的stage index
                {
                    _dutsLastPassStageIndex[i] = _excutePolicyMemberIndex;
                }
            }
            return false;
        }

        /// <summary>
        /// 多阶段测试检查配方阶段
        /// </summary>
        /// <returns> 返回代表是否继续测试</returns>
        bool CheckPolicyNextStageTest(bool withCancelTask)
        {
            AppendLogToDetil($"完成第{_excutePolicyMemberIndex + 1}阶段测试", LOG_TYPE.WARNNING);

            if (_policyManager.Policy.MemberList.Count <= _excutePolicyMemberIndex + 1) // 执行完毕
            {
                return false;
            }


            //  Buffer.BlockCopy(_dutsMangerExecuteFlag, 0, _retryDutsManagerFlag, 0, _dutsMangerExecuteFlag.GetLength(0) * _dutsMangerExecuteFlag.GetLength(1) * sizeof(bool));
            //重新载入测试标记
            for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++)
            {
                int groupId = 0;
                int id = 0;
                DutsLogicalMap.ConventUIdToGroupDutId(i, ref groupId, ref id);
                if (_dutExecuteFlag[i] != false && _dutsErrorCode[i] == DutMaster.ERR_CODE_OK)
                {
                    _dutsMangerExecuteFlag[groupId, id] = _dutExecuteFlag[i];
                }
                else
                {
                    _dutsMangerExecuteFlag[groupId, id] = false; // 排除测试任务
                }
            }
            // 检查是否仍有任务需要执行
            bool hadGroupTask = false;
            for (int i = 0; i < BSTeamConfig.GROUP_COUNT; i++)
            {
                bool foundTask = false;
                for (int j = 0; j < BSTeamConfig.ITEM_DUT_NUM; j++)
                {
                    if (_dutsMangerExecuteFlag[i, j])
                    {
                        foundTask = true;
                        break;
                    }
                }
                if (!foundTask) // 没有dut任务就取消通讯板任务
                {
                    _groupExcuteFlags[i] = false;
                }
                else
                {
                    hadGroupTask = true;
                    _groupExcuteFlags[i] = true;
                }
            }

            if (!withCancelTask
                && hadGroupTask)
            {
                return true;
            }

            // 测试完成
            return false;
        }
        //StartTime,TesterId,DutId,Duration,BinNumber,Result,StateCode,StageCount,Stage1,Stage1Result,Stage2,Stage2Result,Stage3,Stage3Result
        /// <summary>
        /// 保存结果计算分BIN
        /// </summary>
        void SaveLastTestResult()
        {
            string FailDetail = "";
            string EnvBadDetail = "";
            for (int i = 0; i < BSTeamConfig.GROUP_COUNT; i++)
            {
                for (int j = 0; j < BSTeamConfig.ITEM_DUT_NUM; j++)
                {
                    int dutMapId = DutsLogicalMap.ConventIdToUI(j, i);
                    UInt32 recordInstance = _groupRecordInstance[i, j];
                    byte errorCode = _dutsErrorCode[dutMapId];
                    bool execFlag = _dutExecuteFlag[dutMapId];

                    if (execFlag)
                    {
                        byte binCode = BinCodeManager.GetInstance().DefaultBin;
                        DateTime doneTime = _dutsManagerList[i].GetDutFinishDateTime(j);
                        TimeSpan testTime = doneTime - _groupStagesStartTime[i, 0];
                        if (_bsTeamConfig.OrderBinByStage) // 按照段分BIN
                        {
                            BinCodeManager.GetInstance().GetBinNumber((byte)((_dutsLastPassStageIndex[dutMapId] + 1) & 0xff), ref binCode);
                        }
                        else
                        {
                            BinCodeManager.GetInstance().GetBinNumber(errorCode, ref binCode);
                        }
                        _dutsBinCode[dutMapId] = binCode;// 
                        if (recordInstance != CSVRecord.INVALID_INSTANCE_ID)
                        {
                            _csvRecord.AddFixedRecord(recordInstance, $"{ _taskSerialNo.ToString()}-{i + 1}-{j + 1}");
                            _csvRecord.AddFixedRecord(recordInstance, _groupStagesStartTime[i, 0].ToString("yyyy-MM-dd HH:mm:ss"));
                            _csvRecord.AddFixedRecord(recordInstance, doneTime.ToString("yyyy-MM-dd HH:mm:ss"));
                            _csvRecord.AddFixedRecord(recordInstance, Tools.TimeSpanToString(testTime));
                            _csvRecord.AddFixedRecord(recordInstance, "team" + (_instanceId + 1).ToString());

                            _csvRecord.AddFixedRecord(recordInstance, "board" + (i + 1).ToString()); //  只有一个通信板的时候不记录
                            _csvRecord.AddFixedRecord(recordInstance, "dut" + (j + 1).ToString());

                            _csvRecord.AddFixedRecord(recordInstance, binCode);

                            string resultDescription = DutMaster.GetResultDescript(errorCode);
                            _csvRecord.AddFixedRecord(recordInstance, resultDescription);
                            _csvRecord.AddFixedRecord(recordInstance, errorCode);

                            _csvRecord.AddFixedRecord(recordInstance, _dutsExcuteStageCount[i, j]);
                            _csvRecord.SaveRecord(recordInstance, false);
                        }
                        if (errorCode != DutMaster.ERR_CODE_OK)
                        {
                            if (errorCode == DutMaster.ERR_CODE_FAIL1 || errorCode == DutMaster.ERR_CODE_FAIL2)
                            {
                                FailDetail += (dutMapId + 1).ToString() + "[" + _dutsExcuteStageCount[i, j] + "," + errorCode.ToString("X2") + "] ";
                            }
                            else
                            {
                                EnvBadDetail += (dutMapId + 1).ToString() + "[" + _dutsExcuteStageCount[i, j] + "," + errorCode.ToString("X2") + "] ";
                            }
                        }
                    }
                    else
                    {
                        _dutsBinCode[dutMapId] = 0;
                    }
                }
            }
            if (FailDetail.Length > 0)
            {
                AppendLogToDetil($"不良:" + FailDetail, LOG_TYPE.DONE);
            }
            if (EnvBadDetail.Length > 0)
            {
                AppendLogToDetil($"异常:" + EnvBadDetail, LOG_TYPE.DONE);
            }

        }

        void StageFaileDutStatistics()
        {
            _stageFailCount = new UInt32[_policyManager.Policy.MemberList.Count];
            for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++)
            {
                if (!_dutExecuteFlag[i])
                {
                    continue;
                }
                if (_dutsLastPassStageIndex[i] < _policyManager.Policy.MemberList.Count - 1)
                {
                    int faileIndex = _dutsLastPassStageIndex[i] + 1;
                    _stageFailCount[faileIndex]++;
                }
            }
        }

        /// <summary>
        /// 保存当前阶段阶段的测试状态，只在某一个测试完成时保存
        /// </summary>
        void SaveStageTestDetail(int groupId, int dutIndex)
        {
            if (groupId < BSTeamConfig.GROUP_COUNT && dutIndex < BSTeamConfig.ITEM_DUT_NUM)
            {
                string stageInfo = $"[{_policyManager.Policy.MemberList.Count}-{_excutePolicyMemberIndex + 1}]";
                stageInfo += $"[{_excuteCount}]";

                int dutMapId = DutsLogicalMap.ConventIdToUI(dutIndex, groupId);
                TimeSpan stageDuration = _dutsManagerList[groupId].GetDutFinishDateTime(dutIndex) - _groupStagesStartTime[groupId, _excutePolicyMemberIndex];
                UInt32 passCount = _retryPassCount[dutMapId];
                UInt32 failCount = _retryFailCount[dutMapId];
                _csvRecord.AddOneRecord(_groupRecordInstance[groupId, dutIndex], stageInfo);
                _csvRecord.AddOneRecord(_groupRecordInstance[groupId, dutIndex], $"P/F:{passCount}/{failCount}");
                _csvRecord.AddOneRecord(_groupRecordInstance[groupId, dutIndex], Tools.TimeSpanToString(stageDuration));// 记录每一段的时间
                _dutsExcuteStageCount[groupId, dutIndex]++;
            }
        }

    }
}
