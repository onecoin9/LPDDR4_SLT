using Hsg.BLL.config;
using Hsg.BLL.Net;
using Hsg.BLL.Service;
using Hsg.BLL.ViewModel;
using Hsg.Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Hsg.BLL.Model
{
    /// <summary>
    /// 用于内部沟通的事件
    /// </summary>
    public enum DMEvent
    {
        /// <summary>
        /// 初始化完成，用于
        /// </summary>
        EVT_INIT_DONE,

        /// <summary>
        /// MB 配置参数修改
        /// </summary>
        EVT_MB_CONFIG_CHANGE,
        /// <summary>
        /// 板卡上线
        /// </summary>
        EVT_BOARD_ONLINE,
        /// <summary>
        /// 在线检查
        /// </summary>
        EVT_ONLINE_CHECK,
        /// <summary>
        /// 初始化通讯板IO
        /// </summary>
        EVT_INIT_HW_IO,
        /// <summary>
        /// 重置化通讯板IO
        /// </summary>
        EVT_RESET_HW_IO,
        /// <summary>
        /// 准备进入工作状态 ST_WORKING
        /// </summary>
        EVT_ENTRY_WORK_MODE,
        /// <summary>
        /// 退出准备状态回到 ST_IDLE
        /// </summary>
        EVT_EXIT_WORK_MODE,
        /// <summary>
        /// 执行一个测试任务
        /// </summary>
        EVT_EXCUTE_TEST,
        /// <summary>
        /// 给设备上电
        /// </summary>
        EVT_POWER_ON_TEAM,
        /// <summary>
        /// 给设备上电2
        /// </summary>
        EVT_POWER_ON_TEAM2,
        /// <summary>
        /// 发送IO 一组控制指令
        /// </summary>
        EVT_GROUP_IO_CONTROL,
        /// <summary>
        /// 检查是否工作正常
        /// </summary>
        EVT_CON_CHECK,
        /// 退出检查DUT工作正常
        /// </summary>
        EVT_CON_CHECK_TIMEOUT,
        /// 通讯板通讯超时
        /// </summary>
        EVT_TB_COMMUNICATE_TIMEOUT,
        /// 温控板异常
        /// </summary>
        EVT_TC_ABNORMAL,
        /// 重试一次测试
        /// </summary>
        EVT_RETRY_ONCE,
        /// <summary>
        /// 测试完成 失败或者成功
        /// </summary>
        EVT_FINISH,
        /// <summary>
        /// 给设备下电
        /// </summary>
        EVT_POWER_OFF_TEAM,
        /// <summary>
        /// 给部分设备下电
        /// </summary>
        EVT_POWER_OFF_DUTS,
        /// <summary>
        /// 测试时间刷新
        /// </summary>
        EVT_TIME_UPDATE,
        /// <summary>
        /// 测试超时
        /// </summary>
        EVT_TIMEOUT,
        /// <summary>
        /// 取消测试任务
        /// </summary>
        EVT_CANCEL_TASK,
        /// <summary>
        /// 关闭程序
        /// </summary>
        EVT_DESTORY,
        EVT_DUT_POST_MSG,
        /// <summary>
        /// 状态重置，重新扫描
        /// </summary>
        EVT_RSET_STATE,
    }

    public enum IOGROPU_SET_STAGE
    {
        TM_START,
        TM_SPAN,
        TM_END,
    }
    /// <summary>
    /// 通讯板的状态
    /// </summary>
    public enum DMState
    {
        /// <summary>
        ///初始化状态
        /// </summary>
        ST_INIT,
        /// <summary>
        /// 继续检测扫描失败的IP
        /// </summary>
        ST_IDLE,
        /// <summary>
        /// 已经在线，等待开始测试
        /// </summary>
        ST_ONLINE,
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

    public partial class DutsManager : StateMechine<DMState, DMEvent>
    {
        public delegate void IOnDutsManagerStageChange(int teamId, int groupId, TestStage stage);

        private CBCProtocol _cbcControl;
        private MBConfig _mbConfig;
        private int _instanceId;
        private int _groupId;

        private TimerTask _timerTask;
        private int _retryTimerId = TimerTask.INVALID_TIMER_ID;// 任务重试
        private DMEvent _retryEvent;
        private int _retryCount;// 重试计数
        private DateTime _startTime;// 开始测试的时间 
        private IOnDutsManagerStageChange _onStageChange;
        private DutManagerCfg _dutManagerCfg;
        private TempCtrTeam _tempControl;
        private DutPostEventAsync[] _dutPostList;// dut 请求列表
                                                 //  private int _deviceId;
        private const int MAX_RETRY = 2;
        private TestStage _lastState;
        private Object _lastStateObjLock;// lock
                                         //private bool _enable;//标识当前目标组是否处可用
                                         //  private bool _connTimeoutCheck = false;// 标识正在检查连接超时
        private bool _retryAvailable = false;
        private bool _retryTeamTask = false; // 针对连接超时的，在重启通信板后重试一次
                                             //  public bool Enable { get { return _enable; } }
                                             /// <summary>
                                             /// 取消当前任务
                                             /// </summary>
        private bool _bCancellTask = false;
        // private IHsgLogger _logger;
        private TBCommunicateSvr _tbCommunicateService;
        private bool _teamTestFinish;// 测试任务是否完成
        private Timer _syncDutsPwmTimer;
        public DutsManager(int teamId, int groupId, TempCtrTeam tempCtr, ITeamViewModel teamViewModel, int dutNum, IOnDutsManagerStageChange onStageChange) : base("DutsManager" + (teamId + 1).ToString() + "-" + groupId)
        {

            _dutManagerCfg = new DutManagerCfg(teamId, groupId, OnConfigChange);
            _dutList = new List<DutMaster>();
            _lastStateObjLock = new Object();
            _lastState = TestStage.ST_NOT_START;
            _mbConfig = new MBConfig(teamId, groupId, OnMBConfigChange);
            _tempControl = tempCtr;
            _instanceId = teamId;
            _groupId = groupId;

            for (int i = 0; i < dutNum; i++)
            {
                int logicId = DutsLogicalMap.ConventIdToUI(i, _groupId);
                DutMaster dutItem = new DutMaster(teamId, groupId, i, teamViewModel.DutsDetail[logicId], OnDutStageChange, OnRecvDutPostMessage);
                _dutList.Add(dutItem);
            }
            _cbcControl = new HsgCBCProtocol();
            _cbcControl.BindOnlineStateChange(OnBoardStateChange, _dutManagerCfg.IPIndex);
            _tbCommunicateService = TBCommunicateSvr.GetInstance();
            _tbCommunicateService.RegistDataHandle(OnTestBoardDataHandle, _dutManagerCfg.IpAddr);

            uiState = new DMUIState(teamViewModel, groupId);


            _retryTimerId = TimerTask.INVALID_TIMER_ID;
            _timerTask = TimerTask.GetTimerTaskInstance();
            _onStageChange = onStageChange;
            _dutExcuteFlags = new bool[dutNum];
            _dutsErrorCode = new byte[dutNum];
            _dutsStateCode = new ushort[dutNum];
            _dutsLastEvtInfo = new string[dutNum];
            _dutPostList = new DutPostEventAsync[dutNum];
            _dutsFinishTime = new DateTime[dutNum];
            _syncDutsPwmTimer = new Timer(SyncDutsPwmTimerCallback);
            RegisterActionHandle();
        }

        private void OnBoardStateChange(bool online)
        {
            if (online)
            {
                PostEventAsync(DMEvent.EVT_BOARD_ONLINE);
            }
        }
        private void OnMBConfigChange()
        {
            Hlog.I(Mod, "OnMBConfigChange");
            PostEventAsync(DMEvent.EVT_MB_CONFIG_CHANGE);
        }

        private void RegisterActionHandle()
        {
            RegisterStateHandle(DMState.ST_INIT, DMEvent.EVT_INIT_DONE, DoActionFirstInitDone);

            RegisterStateHandle(DMState.ST_IDLE, DMEvent.EVT_BOARD_ONLINE, DoEntryOnlineState);
            RegisterStateHandle(DMState.ST_IDLE, DMEvent.EVT_ONLINE_CHECK, DoActionIdleOnlineCheck);
            RegisterStateHandle(DMState.ST_IDLE, DMEvent.EVT_DESTORY, DoActionDestory);
            RegisterStateHandle(DMState.ST_IDLE, DMEvent.EVT_EXCUTE_TEST, DoActionExcuteTestRetry);


            RegisterStateHandle(DMState.ST_ONLINE, DMEvent.EVT_INIT_HW_IO, DoActionInitBoardHwIo);
            RegisterStateHandle(DMState.ST_ONLINE, DMEvent.EVT_MB_CONFIG_CHANGE, DoActionMbusConfigChange);
            RegisterStateHandle(DMState.ST_ONLINE, DMEvent.EVT_DESTORY, DoActionDestory);
            RegisterStateHandle(DMState.ST_ONLINE, DMEvent.EVT_EXCUTE_TEST, DoActionExcuteTestRetry);

            RegisterStateHandle(DMState.ST_READY, DMEvent.EVT_EXCUTE_TEST, DoActionExcuteTestReq);
            RegisterStateHandle(DMState.ST_READY, DMEvent.EVT_MB_CONFIG_CHANGE, DoActionMbusConfigChange);
            RegisterStateHandle(DMState.ST_READY, DMEvent.EVT_DESTORY, DoActionDestory);
            RegisterStateHandle(DMState.ST_READY, DMEvent.EVT_RSET_STATE, DoActionResetState);


            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_ONLINE_CHECK, DoActionWorkingOnlineCheck);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_RESET_HW_IO, DoActionResetAllIo);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_TIMEOUT, DoActionTimeout);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_POWER_ON_TEAM, DoActionPowerOnTeam);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_GROUP_IO_CONTROL, DoActionSndGroupIOControl);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_CON_CHECK, DoActionEntryDustWorkStateCheck);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_CON_CHECK_TIMEOUT, DoActionDustWorkStateCheckTimeout);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_TB_COMMUNICATE_TIMEOUT, DoActionTbCommunicateTimeout);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_TC_ABNORMAL, DoActionTempCtrBoardAbnormal);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_FINISH, DoActionTestFinish);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_DUT_POST_MSG, DoActionDutPostMsg);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_CANCEL_TASK, DoActionCancelTestWork);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_POWER_OFF_TEAM, DoActionPowerOffTeam);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_RETRY_ONCE, DoActionRetryOnce);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_POWER_OFF_DUTS, DoActionPowerOffDuts);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_BOARD_ONLINE, DoActionCommunicateBoardReboot);
            RegisterStateHandle(DMState.ST_WORKING, DMEvent.EVT_DESTORY, DoActionDestory);

            RegisterStateHandle(DMState.ST_WORKE_END, DMEvent.EVT_EXCUTE_TEST, DoActionExcuteTestReq);
            RegisterStateHandle(DMState.ST_WORKE_END, DMEvent.EVT_DESTORY, DoActionDestory);
            RegisterStateHandle(DMState.ST_WORKE_END, DMEvent.EVT_RSET_STATE, DoActionResetState);
        }
        protected override void NotifyStateChange(DMState state)
        {
            switch (state)
            {
                case DMState.ST_INIT:
                    TestStage = TestStage.ST_NOT_START;
                    DoFistStateInit();
                    break;
                case DMState.ST_IDLE:
                    TestStage = TestStage.ST_NOT_START;
                    DoIdleStateInit();
                    break;
                case DMState.ST_ONLINE:
                    TestStage = TestStage.ST_PREPARE;
                    DoOnlineStateInit();
                    break;
                case DMState.ST_WORKE_END:
                    DoWorkEndStateInit();
                    TestStage = _lastState;
                    break;
                case DMState.ST_READY:
                    TestStage = TestStage.ST_READY;
                    DoReadyStateInit();
                    break;
                case DMState.ST_WORKING:
                    TestStage = TestStage.ST_TESTING;
                    DoWorkStateInit();
                    break;
            }

        }
        #region DO STATE INIT
        private void DoFistStateInit()
        {
            //   Hlog.E("DoActionFirstInit @@@@");
            for (int i = 0; i < _dutList.Count; i++)
            {
                _dutList[i].Run();
            }
            PostEventAsync(DMEvent.EVT_INIT_DONE, CurState);
        }

        private void DoIdleStateInit()
        {
            bool ret = _cbcControl.CheckIpIsReady(_dutManagerCfg.IpAddr); // 这里没有清空记录，如果一次存在，则一直存在
            // Hlog.I("entry idle:" + _instanceId);
            uiState.AddStageDetail("在线检查:" + _dutManagerCfg.IpAddr);
            if (ret)
            {
                // Hlog.I("found ip ok id:" + _instanceId);
                PostEventAsync(DMEvent.EVT_BOARD_ONLINE);
            }
        }

        private void DoOnlineStateInit()
        {
            uiState.DevOnline = true;
            uiState.AddStageDetail("设备已经在线");
            if (_cbcControl.StartConnect(_mbConfig))
            {
                //  Hlog.I(_ModName,"mbus ready success");
                uiState.AddStageDetail("启用端口成功");
                //AppendLogToUi("创建接收端口成功", LOG_TYPE.DONE);
            }
            else
            {
                Hlog.E(Mod, "StartConnect +  mod conn failed");
                uiState.AddStageDetail("启用ModBus失败");
                return;
            }
            uiState.AddStageDetail("开始初始化通讯板");
            //AppendLogToUi("开始读取设备信息", LOG_TYPE.INFO);
            PostEventAsync(DMEvent.EVT_INIT_HW_IO);
            return;
        }

        private void DoReadyStateInit()
        {
            //  uiState.AddStageDetail("ID:" + _deviceId);
            uiState.AddStageDetail("地址:" + _dutManagerCfg.IpAddr.ToString());
            uiState.AddStageDetail("MBUS接收端口:" + _mbConfig.localPort);
            uiState.AddStageDetail("MBUS发送端口:" + _mbConfig.remotePort);
            uiState.AddStageDetail("MBUS地址:" + _mbConfig.slaveId);
        }

        private void DoWorkStateInit()
        {
            float temp = 0;
            bool envIsReay = _tempControl.CheckEnvIsReady();
            _startTime = DateTime.Now;
            _teamTestFinish = false;
            _syncDutsPwmTimer.Change(Timeout.Infinite, Timeout.Infinite);// 关掉 dut 状态关闭请求
            //  _connTimeoutCheck = false;
            // 必须先重置所有工作的dut 状态。避免异步出现部分先完成，部分还未执行而判定结束的 bug
            for (int i = 0; i < _dutExcuteFlags.Length; i++)
            {
                if (_dutExcuteFlags[i])
                {
                    uiState.ResetDutState(i);
                }
            }
            _lastState = TestStage.ST_READY;
            for (int i = 0; i < _dutExcuteFlags.Length; i++)
            {
                int logicId = DutsLogicalMap.ConventIdToUI(i, _groupId);
                if (_dutExcuteFlags[i])// 参与测试的执行测试指令
                {
                    _dutList[i].SetExtraInfo(_stageInfo, _repeatInfo, $"{ _taskSerialNo.ToString()}-{_groupId + 1}-{i + 1}");// 写入关联的附加信息
                    if (envIsReay && !_tempControl.CheckDutEnvReady(logicId, ref temp)) // 检查环境未就绪
                    {
                        uiState.AddStageDetail("[" + (i + 1) + "]环境异常" + temp);
                        _dutList[i].ExcuteOnceTest(_startTimestamp, _testBoardCfg, temp, false);
                    }
                    else
                    {
                        uiState.AddStageDetail("[" + (i + 1) + "]测试中");
                        _dutList[i].ExcuteOnceTest(_startTimestamp, _testBoardCfg, temp, true);
                        int line = _dutManagerCfg.ConventIdToBoard(i);
                        _dutEnableFlags |= (UInt16)(1 << line);
                    }
                }
            }
            _retryCount = 0;

            if (!envIsReay)
            {
                string abnormalInfo = _tempControl.GetStateInfo();
                _retryAvailable = false;
                PostEventAsync(DMEvent.EVT_TC_ABNORMAL);// 发送重置令失败，执行通信失败流程
                AppendLogToDetil(abnormalInfo, LOG_TYPE.ERROR);
                AppendLogToUi(abnormalInfo, LOG_TYPE.ERROR);
                return;
            }

            PostEventAsync(DMEvent.EVT_ONLINE_CHECK);
        }

        private void DoWorkEndStateInit()
        {
            StopRetryTimer();
            if (_bCancellTask)
            {
                //uiState.AddStageDetail("测试任务取消");
                AppendLogToUiSimple("已经测试任务取消:" + Tools.HexToString(_dutsErrorCode), LOG_TYPE.DONE);
                AlarmState = AlarmType.None;// 取消测试不上报异常
                _bCancellTask = false;
            }
            else
            {
                AppendLogToUiSimple("测试结束:" + Tools.HexToString(_dutsErrorCode), LOG_TYPE.INFO);
            }

            for (int i = 0; i < _dutList.Count; i++)
            {
                string detail = string.Format(@"[{0}]", i + 1);
                if (uiState.DutsState[i] > TestStage.ST_TESTING)
                {
                    //string result = uiState.GetDutTestResult(i, uiState.DutsState[i] != TestStage.ST_TEST_TIMEOUT);
                    if (uiState.DutsState[i] == TestStage.ST_TEST_FAIL)
                    {
                        detail += "失败";
                    }
                    else if (uiState.DutsState[i] == TestStage.ST_TEST_TIMEOUT)
                    {
                        detail += "超时";
                    }
                    else
                    {
                        detail += "通过";
                    }
                    //if (result != null)
                    //{
                    //    detail += " ";
                    //    detail += result;
                    //}
                    if (uiState.DutsState[i] != TestStage.ST_TEST_SUCCESS)
                    {
                        AppendLogToDetil(detail, LOG_TYPE.ERROR);
                    }
                    else
                    {
                        AppendLogToDetil(detail, LOG_TYPE.DONE);
                    }

                }
                else
                {
                    detail += "空闲";
                    uiState.AddStageDetail(detail);
                }
            }
        }
        #endregion
        #region do event action
        private DMState DoActionFirstInitDone(object param)
        {
            return DMState.ST_IDLE;
        }

        private DMState DoActionCancelTestWork(object param)
        {
            AppendLogToUiSimple("请求取消测试任务", LOG_TYPE.INFO);
            StopRetryTimer();
            _bCancellTask = true;
            if (_teamTestFinish)
            {
                _retryTeamTask = false;
                PostEventAsync(DMEvent.EVT_POWER_OFF_TEAM);
                return DMState.ST_WORKING;
            }
            else if (!_retryTeamTask) // 正在执行重试
            {
                for (int i = 0; i < _dutList.Count; i++)
                {
                    _dutList[i].CancelTestWork();
                }
            }
            else// 重试过程中，直接结束
            {
                _retryTeamTask = false;
                return DMState.ST_WORKE_END;
            }
            return DMState.ST_WORKING;
        }
        private DMState DoEntryOnlineState(object param)
        {
            uiState.AddStageDetail("侦测到板卡:" + _mbConfig.ipAddr.ToString() + "开始检查网络");
            PostEventAsync(DMEvent.EVT_ONLINE_CHECK);
            // uiState.AddStageDetail("启用接收端口:" + _mbConfig.localPort);
            return DMState.ST_IDLE;
        }
        private DMState DoActionIdleOnlineCheck(object param)
        {
            if (!Tools.PingIp(_dutManagerCfg.IpAddr, 500))
            {
                StartRetryTimer(3000, DMEvent.EVT_ONLINE_CHECK);
            }
            else
            {
                _retryCount = 0;
                return DMState.ST_ONLINE;
            }
            return DMState.ST_IDLE;
        }


        private DMState DoActionInitBoardHwIo(object param)
        {
            if (_cbcControl.InitAllGpio())
            {
                AppendLogToDetil("初始化成功", LOG_TYPE.DONE);
                return DMState.ST_READY;
            }
            else
            {
                //AppendLogToUi("初始化失败，重试", LOG_TYPE.DONE);
                StartRetryTimer(3000, DMEvent.EVT_INIT_HW_IO);
            }

            return DMState.ST_ONLINE;
        }


        private DMState DoActionTimeout(object param)
        {
            for (int i = 0; i < _dutList.Count; i++)
            {
                if (_dutExcuteFlags[i])
                {
                    _dutList[i].ExcuteTimeout();
                }
            }
            return DMState.ST_WORKING;
        }

        private DMState DoActionExcuteTestRetry(object param)
        {
            AppendLogToUiSimple("板卡恢复中, 等待就绪后重试", LOG_TYPE.WARNNING);
            StartRetryTimer(5000, DMEvent.EVT_EXCUTE_TEST);
            return CurState;
        }

        private DMState DoActionExcuteTestReq(object param)
        {
            TimeSpan span = DateTime.Now.ToUniversalTime() - new DateTime(1970, 1, 1, 0, 0, 0);
            int delayMsecond = 0;
            if (param != null)
            {
                int.TryParse(param.ToString(), out delayMsecond);
            }
            if (delayMsecond > 0)
            {
                StartRetryTimer(delayMsecond, DMEvent.EVT_EXCUTE_TEST);
                return DMState.ST_READY;
            }
            AlarmState = AlarmType.None;
            _dutEnableFlags = 0;
            _retryAvailable = true;
            _startTimestamp = (uint)span.TotalSeconds;
            //uiState.AddStageDetail("开始执行测试");
            AppendLogToDetil("开始执行测试", LOG_TYPE.INFO);
            return DMState.ST_WORKING;
        }

        private DMState DoActionMbusConfigChange(object param)
        {
            if (CurState >= DMState.ST_ONLINE)
            {
                if (_retryCount < MAX_RETRY)
                {
                    StartRetryTimer(3000, DMEvent.EVT_POWER_ON_TEAM);
                }
                _cbcControl.Destory();
            }
            return DMState.ST_IDLE;
        }

        private DMState DoActionWorkingOnlineCheck(object param)
        {
            if (!Tools.PingIp(_dutManagerCfg.IpAddr, 1000))
            {
                if (_retryCount < MAX_RETRY + 3) // 给予20S
                {
                    StartRetryTimer(3000, DMEvent.EVT_ONLINE_CHECK);
                }
                else
                {
                    _retryAvailable = false;
                    PostEventAsync(DMEvent.EVT_TB_COMMUNICATE_TIMEOUT);// 发送重置令失败，执行通信失败流程
                    AppendLogToDetil("通讯网络Ping不通", LOG_TYPE.ERROR);
                }
            }
            else
            {
                _retryCount = 0;
                PostEventAsync(DMEvent.EVT_RESET_HW_IO);
            }
            return DMState.ST_WORKING;
        }
        private DMState DoActionResetAllIo(object param)
        {
            if (!_cbcControl.ResetAllGpio())
            {
                if (_retryCount < MAX_RETRY) //
                {
                    StartRetryTimer(4000, DMEvent.EVT_RESET_HW_IO);
                }
                else
                {
                    _retryAvailable = false;
                    PostEventAsync(DMEvent.EVT_TB_COMMUNICATE_TIMEOUT);// 发送重置令失败，执行通信失败流程
                    AppendLogToDetil("通讯请求重置IO失败", LOG_TYPE.ERROR);
                }
            }
            else
            {
                AppendLogToDetil("ResetIO完成", LOG_TYPE.INFO);
                _retryCount = 0;
                //PostEventAsync(DMEvent.EVT_POWER_ON_TEAM);// 发送上电指令
                StartRetryTimer(1000, DMEvent.EVT_POWER_ON_TEAM); // 延迟1S上电，错开reset 时间
            }
            return DMState.ST_WORKING;
        }

        private DMState DoActionPowerOnTeam(object param)
        {
            Hlog.I(Mod, "send command powerset" + _dutEnableFlags.ToString("X2"));
            if (!_cbcControl.PowerSet((ushort)(_dutEnableFlags)))
            {
                if (_retryCount < MAX_RETRY)
                {
                    StartRetryTimer(3000, DMEvent.EVT_POWER_ON_TEAM);
                }
                else
                {
                    _retryAvailable = false;
                    PostEventAsync(DMEvent.EVT_TB_COMMUNICATE_TIMEOUT);// 发送上电指令失败，执行通信失败流程
                }
            }
            else
            {

                // set io group
                if (_dutManagerCfg.IOCtrAId < (ushort)EIOGroup.SWITCH_GROUP_NUM)
                {
                    _cbcControl.StartNewIOControl();
                    PostEventAsync(DMEvent.EVT_GROUP_IO_CONTROL);
                }
                else
                {
                    PostEventAsync(DMEvent.EVT_CON_CHECK);
                    return DMState.ST_WORKING;
                }
            }
            return DMState.ST_WORKING;
        }
        private DMState DoActionSndGroupIOControl(object param)
        {
            // Hlog.E("DoActionExcuteTestReq @@@@ ");
            ushort[] setPackage = Array.Empty<ushort>();
            CBCProtocol.GenerateIoSecuritySetPackage(_cbcControl.GetIOControlSerial(), _dutManagerCfg.IOCtrAId,
                                                _dutManagerCfg.IOCtrBatch,
                                                _dutManagerCfg.IOCtrAStart,
                                               (_dutManagerCfg.IOCtrSetIntervalSec),
                                                (ushort)(_dutManagerCfg.IOCtrASpan * 1000),
                                                out setPackage);

            if (!_cbcControl.SetIOSecurityControl(setPackage))
            {
                if (_retryCount < MAX_RETRY)
                {
                    StartRetryTimer(3000, DMEvent.EVT_GROUP_IO_CONTROL);
                }
                else
                {
                    _retryAvailable = false;
                    PostEventAsync(DMEvent.EVT_TB_COMMUNICATE_TIMEOUT);// 发送上电指令失败，执行通信失败流程
                }
            }
            else
            {
                StartRetryTimer((_dutManagerCfg.IOCtrAStart + _dutManagerCfg.IOCtrBatch * _dutManagerCfg.IOCtrSetIntervalSec) * 1000, DMEvent.EVT_CON_CHECK);
            }
            return DMState.ST_WORKING;
        }

        private DMState DoActionEntryDustWorkStateCheck(object param)
        {
            //_connTimeoutCheck = true;
            _retryTeamTask = false;
            if (_dutManagerCfg.DutConnectTimeoutSecond > 0)
            {
                StartRetryTimer(_dutManagerCfg.DutConnectTimeoutSecond * 1000, DMEvent.EVT_CON_CHECK_TIMEOUT);
            }
            return DMState.ST_WORKING;
        }

        private DMState DoActionDustWorkStateCheckTimeout(object param)
        {
            bool hadNormalConn = false;
            List<Int32> notStartedList = new List<Int32>();// 记录测试dut 未收到Ready的单元
            string timeDutCnt = "";
            for (int i = 0; i < _dutList.Count; i++)
            {
                if (!_dutExcuteFlags[i])
                {
                    continue;
                }
                if (!_dutList[i].TestIsStarted())
                {
                    notStartedList.Add(i);
                    timeDutCnt += "Dut" + (i + 1).ToString() + " ";

                }
                else
                {
                    hadNormalConn = true;
                }
            }
            if (timeDutCnt.Length > 0)
            {
                AppendLogToUiSimple("测试板启动超时:" + timeDutCnt, LOG_TYPE.ERROR);
            }

            // 未正常启动的处理
            foreach (int i in notStartedList)
            {
                if (!hadNormalConn && _retryAvailable)// 所有都未正常启动，且支持重试的取消任务
                {
                    _dutList[i].CancelTestWork();
                }
                else // 其他执行超时处理
                {
                    _dutList[i].ExcuteConnTimeout();
                }
            }
            if (hadNormalConn)
            {
                return DMState.ST_WORKING;
            }
            if (!_dutManagerCfg.DiagnosticMode) // 验机模式，不支持重测。
            {
                if (_retryAvailable)
                {
                    _retryTeamTask = true;
                }
                else
                {
                    _retryTeamTask = false;
                }
            }
            return DMState.ST_WORKING;
        }

        private DMState DoActionTbCommunicateTimeout(object param)
        {
            AlarmState = AlarmType.TBNet;
            for (int i = 0; i < _dutList.Count; i++)
            {
                _dutList[i].ExcuteTBCommunicateTimeout();
            }
            return DMState.ST_WORKING;
        }

        private DMState DoActionTempCtrBoardAbnormal(object param)
        {
            AlarmState = AlarmType.TCNet;
            for (int i = 0; i < _dutList.Count; i++)
            {
                _dutList[i].ExcuteTempCtrBoardAbnormal();
            }
            return DMState.ST_WORKING;
        }

        private DMState DoActionTestFinish(object param)
        {
            StopRetryTimer();
            for (int i = 0; i < _dutList.Count; i++)
            {
                _dutsErrorCode[i] = _dutList[i].GetErrorCode();
                _dutsStateCode[i] = _dutList[i].GetAbnormalStatusCode();
                _dutsLastEvtInfo[i] = _dutList[i].GetLastEnvTemp().ToString();
            }
            _retryCount = 0;
            _teamTestFinish = true;
            PostEventAsync(DMEvent.EVT_POWER_OFF_TEAM);
            return DMState.ST_WORKING;
        }



        private DMState DoActionRetryOnce(object param)
        {
            _dutEnableFlags = 0;
            _retryAvailable = false;
            AppendLogToUiSimple("尝试重新执行测试", LOG_TYPE.WARNNING);
            _retryTeamTask = false;
            DoWorkStateInit();
            return DMState.ST_WORKING;
        }

        private DMState DoActionPowerOffDuts(object param)
        {
            _cbcControl.SyncPowerStatus();
            return DMState.ST_WORKING;
        }
        private DMState DoActionCommunicateBoardReboot(object param)
        {
            if (!_communicateBoardRebootCheck)
            {
                return DMState.ST_WORKING; ;
            }
            for (int i = 0; i < _dutList.Count; i++)
            {
                _dutList[i].ExcuteTBCommunicateTimeout();
            }
            return DMState.ST_WORKING;
        }
        private DMState DoActionPowerOffTeam(object param)
        {
            _syncDutsPwmTimer.Change(Timeout.Infinite, Timeout.Infinite);// 清除dut 同步请求
            if (!_cbcControl.PowerOffAll() && _retryCount < MAX_RETRY)
            {
                StartRetryTimer(2000, DMEvent.EVT_POWER_OFF_TEAM);
                return DMState.ST_WORKING;
            }
            if (_retryTeamTask)
            {
                _cbcControl.RebootAll();
                StartRetryTimer(5000, DMEvent.EVT_RETRY_ONCE);
                return DMState.ST_WORKING;
            }
            if (!_tempControl.CheckEnvIsReady())
            {
                AlarmState = AlarmType.TCNet;// 温控异常
            }
            return DMState.ST_WORKE_END;
        }

        private DMState DoActionDestory(object param)
        {
            StopRetryTimer();
            for (int i = 0; i < _dutList.Count; i++)
            {
                _dutList[i].Destory();
            }
            return DMState.ST_DESTORY;
        }

        private DMState DoActionDutPostMsg(object param)
        {
            for (int i = 0; i < _dutPostList.GetLength(0); i++)
            {
                int instanceId = _dutPostList[i].instanceId;
                if (!_dutPostList[i].valid)
                {
                    continue;
                }
                int dutIndex = -1;
                for (int j = 0; j < _dutList.Count; j++)
                {
                    if (_dutList[i]._instanceId == instanceId)
                    {
                        dutIndex = i;
                        break;
                    }
                }
                if (dutIndex >= 0 && _dutPostList[i].evt == DutEvent_E.DUT_EVT_SET_PWR_KEY)
                {
                    ushort[] sendPackage;
                    IoControl ioControl = new IoControl();
                    PowerSet setValue = _dutList[dutIndex].powerSet;
                    ioControl.groupId = (ushort)EIOGroup.SWITCH_GROUP_MCU_PWR;
                    ioControl.line = (byte)_dutManagerCfg.ConventIdToBoard(dutIndex);



                    ioControl.startSec = setValue.startSec;
                    ioControl.durationMsec = setValue.spanMsec;
                    if (CBCProtocol.GenerateIOSetPackage(ioControl.groupId,
                                                                ioControl.line,
                                                                ioControl.startSec,
                                                                ioControl.durationMsec,
                                                                out sendPackage))
                    {
                        if (!_cbcControl.SetIOControl(sendPackage)) // no retry fixe me.
                        {
                            Hlog.E(Mod, "send io contro failed");
                        }
                    }

                }
                // reset 
                _dutPostList[i].valid = false;
            }
            return DMState.ST_WORKING;
        }

        private DMState DoActionResetState(object param)
        {
            uiState.DevOnline = false;
            _cbcControl.ClearReadyState(_dutManagerCfg.IpAddr);
            return DMState.ST_IDLE;
        }
        #endregion

        #region mbus
        //private void OnMBRecvPrint(string msg)
        //{
        //    Hlog.I(Mod, "MB recv:" + msg);
        //}
        #endregion
        #region timeout retry
        private void StartRetryTimer(int msecond, DMEvent eventId)
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
            Hlog.I(Mod, "start retry timer team:" + _instanceId);
        }
        private void StopRetryTimer()
        {
            if (_retryTimerId != TimerTask.INVALID_TIMER_ID)
            {
                Hlog.I(Mod, "stop retry timer team:" + _retryTimerId);
                _timerTask.StopTimer(ref _retryTimerId);
            }
            _retryCount = 0;
        }
        private void RetryActionTimeout(int timerId)
        {
            // Hlog.I(Mod, "retry action timeout team:" + _instanceId);
            if (timerId == _retryTimerId)
            {
                _retryTimerId = TimerTask.INVALID_TIMER_ID;
                PostEventAsync(_retryEvent);
            }
        }

        #endregion
        void OnConfigChange()
        {

        }

        private void OnTestBoardDataHandle(int portId, byte[] data)
        {
            if (portId < _dutList.Count)
            {
                _dutList[portId].RecvDataHandle(data);
            }
        }
        private void OnRecvDutPostMessage(DutEvent_E evt, int instanceId)
        {
            if (CurState == DMState.ST_WORKING)
            {
                _dutPostList[instanceId].evt = evt;
                _dutPostList[instanceId].instanceId = instanceId;
                _dutPostList[instanceId].valid = true;
                PostEventAsync(DMEvent.EVT_DUT_POST_MSG);
            }
        }


        private void OnDutStageChange(int dutId, TestStage stage)
        {
            TestStage nextStage = TestStage.ST_TEST_SUCCESS;
            bool testFinish = false;
            //if (stage > TestStage.ST_TESTING)// 先同步结果，避免多线程死机
            //{
            //    uiState.SetDutTestResult(dutId, _dutList[dutId].GetTestTime(), _dutList[dutId].GetTestInfor(), _dutList[dutId].GetStatusCode());
            //    uiState.AddDutDetails(dutId, _dutList[dutId].uiState.stageDetails);
            //}
            if (stage == TestStage.ST_NOT_START)
            {
                uiState.ResetDutDetails(dutId);
            }else if(stage > TestStage.ST_TESTING)
            {
                _dutsFinishTime[dutId] = DateTime.Now;// 赋值结束时间
            }
            uiState.DutsState[dutId] = stage;// 更新状态
            if (stage > TestStage.ST_TESTING)
            {
                int powerLine = _dutManagerCfg.ConventIdToBoard(dutId);
                if (powerLine >= 0)
                {
                    _cbcControl.PowerChange(false, (uint)powerLine);
                }
                for (int i = 0; i < uiState.DutsState.Length; i++)
                {
                    if (!_dutList[i].IsFreeMode())
                    {
                        if (uiState.DutsState[i] <= TestStage.ST_TESTING)
                        {
                            testFinish = false;
                            break;
                        }
                        else if (nextStage != TestStage.ST_TEST_TIMEOUT
                                  && nextStage != uiState.DutsState[i]
                                  && uiState.DutsState[i] != TestStage.ST_TEST_SUCCESS)
                        {
                            nextStage = uiState.DutsState[i];
                        }
                        testFinish = true;
                    }
                }
                _syncDutsPwmTimer.Change(1000, Timeout.Infinite);//通知需要同步PWR状态
            }


            if (testFinish)
            {
                // uiState.stage = nextStage;
                lock (_lastStateObjLock)
                {
                    if (_lastState != nextStage)
                    {
                        _lastState = nextStage;
                        PostEventAsync(DMEvent.EVT_FINISH);
                    }
                }

            }
        }


        void SyncDutsPwmTimerCallback(object state)
        {
            PostEventAsync(DMEvent.EVT_POWER_OFF_DUTS);//通知需要同步PWR状态
        }
    }


}

