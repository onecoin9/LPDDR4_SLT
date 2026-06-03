using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Threading;
using Hsg.Common;
using Hsg.BLL.Net;
using System.Net;
using Hsg.BLL.config;
using System.IO;
using Hsg.BLL.Policy;
using Hsg.BLL.ViewModel;
using Hsg.BLL.Service;
using Hsg.Common.ADO;
using System.Collections.Concurrent;
using Newtonsoft.Json.Linq;

namespace Hsg.BLL.Model
{
    public enum BSCEvent
    {
        /// <summary>
        /// 执行当前状态默认任务，加载相关信息
        /// </summary>
        EVT_INIT_DONE,
        /// <summary>
        /// 与PLC 尝试连接
        /// </summary>
        //EVT_CON_PLC_REQ,
        /// <summary>
        /// 按键启动测试服务
        /// </summary>
        EVT_START_SERVICE,
        /// <summary>
        /// 同步handler 机台的温度状况
        /// </summary>
        EVT_SYNC_TMP_STATUS,
        /// <summary>
        /// 同步handler 机台的duts状况
        /// </summary>
        EVT_SYNC_DUTS_STATUS,
        /// <summary>
        /// 按键停止测试
        /// </summary>
        EVT_STOP_SERVICE,
        /// <summary>
        ///关闭程序退出测试
        /// </summary>
        EVT_DESTORY,
        /// <summary>
        /// 上报测试结果或者警告
        /// </summary>
        EVT_REPORT_MSG,
        /// <summary>
        /// 接收到测试上报结果ack
        /// </summary>
        EVT_RECV_RESULT_ACK,
        /// <summary>
        /// 接收到预警上报结果ack
        /// </summary>
        EVT_RECV_ALARM_ACK,
        /// <summary>
        /// 收到同步温度的结果
        /// </summary>
        EVT_RECV_SYNC_SUCCESS,
        /// <summary>
        /// 所有测试组就绪
        /// </summary>
        EVT_ALL_TEAM_READY,
        /// <summary>
        /// 检查测试组就绪
        /// </summary>
        EVT_CHECK_TEAM_READY,
        /// <summary>
        /// 测试组就超时
        /// </summary>
        EVT_TEAM_READY_TIMEOUT,
    }

    public enum BSCStatus
    {
        /// <summary>
        /// 初始状态,创建各路通讯板管理对象
        /// </summary>
        ST_INIT,
        /// <summary>
        /// 进入环境检查，温度，duts 状态等。
        /// </summary>
        ST_IDLE,
        ///// <summary>
        ///// 测试盒就绪，进入就绪状态（或者等待超时）
        ///// </summary>
        ST_Ready,
        /// <summary>
        ///同时按键启动测试，进入工作状态，接受开始测试，上报测试结果
        /// </summary>
        ST_WORKING,
        /// <summary>
        /// 按键退出测试
        /// </summary>
        ST_STOP
    }


    public partial class BSController : StateMechine<BSCStatus, BSCEvent>
    {

        // 用于和测试板通讯
        private List<BSTeam> _teamList;
        // 用于和控制机台通讯
        private TcpClientConn _tcpClient;
        // tester主动上报通道（长连接）
        private TcpClientConn _tcpTxClient;
        private TcpClientConfig _tcpConfig;

        private TimerTask _timerTask;
        private BSCEvent _retryEvent;
        // private BSCEvent _circleEvent;
        //用于失败重试
        private int _retryTimerId = TimerTask.INVALID_TIMER_ID;
        private int _workTimerId = TimerTask.INVALID_TIMER_ID;
        // private List<DutConn> _dutsConnList;
        private TBCommunicateSvr _tbCommunicateService;
        private bool _dutsConnReady;
        private bool[] _teamTestFinshFlags;// 测试完成，等待上报的状态,true 等待汇报，false 没有上报要求
        private SortedList<Int32, Tuple<bool[], DateTime>> _checkReadyList;// 用于检查对应测试盒是否就绪
        private int _lastReportTeamId = 0;
        //private IHsgLogger _logger;
        private ITeamViewModel[] _teamViewModes;
        private bool _initDone = false;
        private SysConfig _sysConfig = SysConfig.GetInstance();
        private DateTime _serverStartTime;//
        private TimeSpan _workHistoryTime;
        private byte[] _decodeDataBuf;
        private const int BUF_SIZE = 4096;
        private int _recvLeftLen = 0;
        private readonly object _opLock = new object();
        private SortedList<int, string> _alarmList;
        private DateTime _startWorkTime;//收到任务开始测试的时间
        private DateTime _stopWorkTime;//最后完成任务的时间
        private bool _recordStart = false;// 记录工作开始
        private UInt32[] _stateFailStatistics;// 记录每一段的失败数量
        //private bool _idleNeedCheckReady = false;// 待机需要检查就绪状态
        private int _checkReadyTimer = TimerTask.INVALID_TIMER_ID;
        public BSController(IHsgLogger logger, IBSViewModel vewModel, ITeamViewModel[] teamViewModes) : base("BSController")
        {
            _viewModel = vewModel;
            _teamViewModes = teamViewModes;
            _teamList = new List<BSTeam>();
            _alarmList = new SortedList<int, string>();
            // 用于任务重试或者轮询
            _timerTask = TimerTask.GetTimerTaskInstance();
            _teamTestFinshFlags = new bool[SysConfig.DEV_NUM];
            // 测试板通讯服务
            _tbCommunicateService = TBCommunicateSvr.GetInstance();
            _checkReadyList = new SortedList<int, Tuple<bool[], DateTime>>();
            _decodeDataBuf = new byte[BUF_SIZE];
            _bsConfig = new BSConfig(OnConfigChange);
            TestRecord = new BSRecord(TEST_RECORD_NAME, _bsConfig.RecordFixeTitle);
            DetailRecord = new BSRecord(DETAIL_RECORD_NAME, _bsConfig.DetailFixeTitle);
            _overviewRecord = new BSRecord(OVERVIEW_RECORD_NAME, _bsConfig.OverviewTitle, true);
            _binRecord = new UInt32[SysConfig.MAX_BIN_COUNT];
            _viewModel.ServiceReady = false;
            AlarmService.instance.BindSendFunction(AddAlarmMsgToReport);
            RegisterEventHandle();
            Hlog.D(MOD_ID, "create BSController object done.");
        }
        /// <summary>
        /// 注册状态机事务处理
        /// </summary>
        private void RegisterEventHandle()
        {
            RegisterStateHandle(BSCStatus.ST_INIT, BSCEvent.EVT_INIT_DONE, this.DoActionFirstInitDone);

            RegisterStateHandle(BSCStatus.ST_IDLE, BSCEvent.EVT_DESTORY, this.DoActionServiceDestory);
            RegisterStateHandle(BSCStatus.ST_IDLE, BSCEvent.EVT_ALL_TEAM_READY, this.DoActionAllTeamReady);
            RegisterStateHandle(BSCStatus.ST_IDLE, BSCEvent.EVT_TEAM_READY_TIMEOUT, this.DoActionTeamReadyTimeout);

            RegisterStateHandle(BSCStatus.ST_Ready, BSCEvent.EVT_START_SERVICE, this.DoActionServiceStart);
            RegisterStateHandle(BSCStatus.ST_Ready, BSCEvent.EVT_STOP_SERVICE, this.DoActionServiceStop);
            RegisterStateHandle(BSCStatus.ST_Ready, BSCEvent.EVT_DESTORY, this.DoActionServiceDestory);
            RegisterStateHandle(BSCStatus.ST_Ready, BSCEvent.EVT_CHECK_TEAM_READY, this.DoActionCheckTeamStateReady);


            RegisterStateHandle(BSCStatus.ST_WORKING, BSCEvent.EVT_STOP_SERVICE, this.DoActionServiceStop);
            RegisterStateHandle(BSCStatus.ST_WORKING, BSCEvent.EVT_REPORT_MSG, this.DoActionReportMessage);
            RegisterStateHandle(BSCStatus.ST_WORKING, BSCEvent.EVT_RECV_RESULT_ACK, this.DoActionRecvRetAck);
            RegisterStateHandle(BSCStatus.ST_WORKING, BSCEvent.EVT_RECV_ALARM_ACK, this.DoActionRecvAlarmAck);
            RegisterStateHandle(BSCStatus.ST_WORKING, BSCEvent.EVT_CHECK_TEAM_READY, this.DoActionCheckTeamStateReady);
            RegisterStateHandle(BSCStatus.ST_WORKING, BSCEvent.EVT_DESTORY, this.DoActionServiceDestory);

        }
        /// <summary>
        /// 状态发生变化
        /// </summary>
        /// <param name="state"></param>
        protected override void NotifyStateChange(BSCStatus state)
        {
            //Hlog.I(MOD_ID, "New state:" + state);
            switch (state)
            {
                case BSCStatus.ST_INIT:
                    DoFirstStateInit();
                    break;
                case BSCStatus.ST_Ready:
                    DoReadStateInit();
                    break;
                default:
                    break;
            }
        }
        #region state init 
        private async void DoFirstStateInit()
        {
            await Task.Delay(1000);
            AppendLogToUi("开始初始化....", LOG_TYPE.WARNNING);
            _dutsConnReady = false;

            // 加载配置文件
            LoadPolicyFile();
            // 创建 team 成员
            for (int i = 0; i < SysConfig.DEV_NUM; i++)
            {
                BSTeam team = new BSTeam(i, _teamViewModes[i], OnBSTeamStageChange);
                _teamList.Add(team);
                BindTeamUIUpdate(i);
            }
            Hlog.I(Mod, "MaterialNo:" + SysConfig.MaterialNo);
            Hlog.I(Mod, "OrderNo:" + SysConfig.OrderNo);
            Hlog.I(Mod, "WorkOrderNo:" + SysConfig.WorkOrderNo);
            //AppendLogToUi("初始化TCP服务", LOG_TYPE.INFO);
            // 创建TCP 服务 和 控制机台联系
            _tcpClient = new TcpClientConn(OnTCPRecvDataHandle, OnTCPConnectChange);
            _tcpTxClient = new TcpClientConn(OnTxRecvDataHandle, OnTxConnectChange);
            _tcpConfig = new TcpClientConfig(OnTcpConfigChange);
            String defaultPath = AppDomain.CurrentDomain.BaseDirectory + "Config";
            if (!Directory.Exists(defaultPath))
            {
                Directory.CreateDirectory(defaultPath);
            }
            AppendLogToUi("启动子状态", LOG_TYPE.INFO);
            //启动子状态
            for (int i = 0; i < _teamList.Count; i++)
            {
#if DEBUG
                if (i > 0)
                {
                    break;
                }
#endif
                _teamList[i].Run();
                // Hlog.I("run team id:" + i);
                //Thread.Sleep(50);
                // await Task.Delay(50);
            }

            //启动UDP接收
            //AppendLogToUi("启动UDP接收", LOG_TYPE.INFO);
            Hlog.I(MOD_ID, "start udp recv port");
            string errorMsg = "";
            bool hadFail = _tbCommunicateService.StartService(ref errorMsg);

            if (hadFail)
            {
                AppendLogToUi(errorMsg, LOG_TYPE.ERROR);
            }

            if (hadFail)
            {
                AppendLogToUi("启动UDP接收端口,存在部分失败", LOG_TYPE.ERROR);
            }
            else
            {
                _dutsConnReady = true;
                AppendLogToUi("启动UDP接收端口完成", LOG_TYPE.INFO);
            }

            //启动命名管道
            // _namePipeSvr.StartService();
            _initDone = true;
            _startWorkTime = DateTime.Now;
            AppendLogToUi("系统初始化结束", LOG_TYPE.WARNNING);

            if (SysConfig.WorkMode == WorkMode.Slave)
            {
                string error = "";
                MesClientService service = MesClientService.GetInstance();
                if (!CheckWorkEnvironment(ref error))
                {
                    service.OnLaunchError(error);
                }
                StartTimeoutRetry(3000, BSCEvent.EVT_TEAM_READY_TIMEOUT);// mes 模式3S 后启动服务
            }
            else if (_bsConfig.TeamReadyTimeout > 0)
            {
                StartTimeoutRetry(_bsConfig.TeamReadyTimeout * 1000, BSCEvent.EVT_TEAM_READY_TIMEOUT);
            }
            PostEventAsync(BSCEvent.EVT_INIT_DONE);
            // return BSCStatus.ST_IDLE;
        }
        private void DoReadStateInit()
        {
            StopTimeoutRetry();
            if (SysConfig.WorkMode == WorkMode.Slave)
            {
                string error = "";
                MesClientService service = MesClientService.GetInstance();
                if (CheckWorkEnvironment(ref error))
                {
                    PostEventAsync(BSCEvent.EVT_START_SERVICE);
                    service.OnLaunchOK(this);
                }
            }

            _viewModel.ServiceReady = true;
        }

        private static bool IsWildcardListenIp(string ip)
        {
            return string.IsNullOrWhiteSpace(ip) || ip == "0.0.0.0" || ip == "::";
        }

        private void EnsureTxChannelConnected()
        {
            string remoteIp;
            ushort remotePort;
            if (_tcpClient != null && _tcpClient.TryGetRemoteEndpoint(out remoteIp, out remotePort))
            {
                _tcpTxClient?.OpenConn(remoteIp, _tcpConfig.HandlerReplyPort);
                Hlog.I(Mod, $"tx channel connect target:{remoteIp}:{_tcpConfig.HandlerReplyPort}");
                return;
            }
            if (!IsWildcardListenIp(_tcpConfig.DestIp))
            {
                _tcpTxClient?.OpenConn(_tcpConfig.DestIp, _tcpConfig.HandlerReplyPort);
                Hlog.I(Mod, $"tx channel fallback target:{_tcpConfig.DestIp}:{_tcpConfig.HandlerReplyPort}");
            }
        }
        #endregion
        /// <summary>
        /// 状态机逻辑处理
        /// </summary>
        /// <returns></returns>
        #region ACTIONS 

        private BSCStatus DoActionFirstInitDone(object param)
        {
            return BSCStatus.ST_IDLE;
        }

        private BSCStatus DoActionCheckTeamStateReady(object param)
        {
            // 旧 CHECK_READY 协议已下线，JSON 协议不再使用该流程。
            // 新协议里这一块不再叫 CHECK_READY 轮询，而是改成请求-应答式处理，入口在 OnTCPRecvDataHandle() 的 JSON 分发。
            // 当前实现对应关系是：
            // TryHandleJsonRequest(...)
            // 收到 JSON 后按 method 分支处理（teststart/getversion/lotstart/...）
            // 处理完成后直接 SendJsonResponse(method, "success|fail", data) 回包
            // 也就是说，旧的“队列 + 定时器 + 重复检查 ready”被替换成了“当次请求当次返回”。
            // 如果要补齐“新协议下的 ready 检查语义”，建议这样做：
            // 在协议里增加一个 method（例如 checkready，文档若有统一命名按文档）
            // 在 TryHandleJsonRequest(...) 里新增分支：
            // 复用你原来 CheckTeamReady 的核心判断逻辑（服务是否启动、team 状态、结果是否已上报）
            // 直接返回 JSON：
            // status: "success" + data.ready = true/false
            // 或 status: "fail" + data.reason
            // 不再用 _checkReadyList / _checkReadyTimer，因为 JSON 已经是同步应答模型

            return CurState;
        }

        private BSCStatus DoActionServiceStart(object param)
        {
            // Hlog.E("DoActionServiceStart notify tcp mgr ready and notify team open conn @@@@@@@ NotImplemented");
            AppendLogToUi("启动测试服务", LOG_TYPE.WARNNING);
            if (_viewModel.HandleServerConnState != ConnState.CONNECTED)
            {
                ConnectPLCServer();
            }
            // 主动上报链路：保持长连接到上报口
            EnsureTxChannelConnected();
            _viewModel.ServiceStart = true;
            for (int i = 0; i < _teamList.Count; i++)
            {
                _teamList[i].EntryWorkMode();
            }
            StartWorkTimerCount();
            return BSCStatus.ST_WORKING;
        }

        private BSCStatus DoActionServiceStop(object param)
        {
            _viewModel.ServiceStart = false;
            DisconnectPLCServer();
            _tcpTxClient.CloseConn();
            StopWorkTimerCount();
          
            for (int i = 0; i < _teamList.Count; i++)
            {
                _teamList[i].ExitWorkMode();
                _teamTestFinshFlags[i] = false;
            }
            return BSCStatus.ST_Ready;
        }


        /// <summary>
        /// 
        /// </summary>
        /// <returns></returns>
        private bool ReportTestResult(ref bool sendOk)
        {
            bool hadTask = false;
            for (int i = 0; i < SysConfig.DEV_NUM; i++)
            {
                if (_teamTestFinshFlags[i])
                {
                    byte[] binNumbers = _teamList[i].GetDutsBinCode();
                    List<int> siteResults = new List<int>(binNumbers.Length);
                    for (int siteIdx = 0; siteIdx < binNumbers.Length; siteIdx++)
                    {
                        // 协议约定：0=禁用, 1=良品, 2=不良(其余可扩展)
                        if (binNumbers[siteIdx] == 0)
                        {
                            siteResults.Add(0);
                        }
                        else if (binNumbers[siteIdx] == 1)
                        {
                            siteResults.Add(1);
                        }
                        else
                        {
                            siteResults.Add(2);
                        }
                    }
                    byte[] outData = HCProtocol.EncodeTestEndJson(i + 1, siteResults);
                    Hlog.I(Mod, "report handler json:" + Encoding.UTF8.GetString(outData));
                    RemoveAlarmMsgForReprot(i); // 上报结果前清除 报警，避免测试完还报警
                    hadTask = true;
                    _lastReportTeamId = i + 1;
                    bool sendRet = SendToHandlerByClient(outData);
                    if (sendRet)
                    {
                        // _teamTestFinshFlags[i] = false;
                        sendOk = true;
                        Hlog.I(Mod, "send test result ok wait ack.");
                    }
                    else
                    {
                        Hlog.E(Mod, "report ret send test result failed. wait retry");
                        _lastReportTeamId = 0;
                        sendOk = false;
                    }
                    break;
                }
            }
            return hadTask;
        }
        private bool ReportAlarmMsg(ref bool sendOk)
        {
            bool hadTask = false;
            int sendKey = -1;
            lock (_opLock)
            {
                if (_alarmList.Keys.Count > 0)
                {
                    sendKey = _alarmList.Keys[0];
                    hadTask = true;
                }
            }
            if (hadTask)
            {
                SendAlarmToServer(sendKey + 1, _alarmList[sendKey]);
            }
            return hadTask;
        }
        private BSCStatus DoActionReportMessage(object param)
        {
            bool sendOk = true;
            // 上报信息
            if (!ReportTestResult(ref sendOk) && !ReportAlarmMsg(ref sendOk))
            {
                return BSCStatus.ST_WORKING;
            }
            if (!sendOk)
            {
                StartTimeoutRetry(3000, BSCEvent.EVT_REPORT_MSG);
            }
            else
            {
                StartTimeoutRetry(1500, BSCEvent.EVT_REPORT_MSG);
            }
            return BSCStatus.ST_WORKING;
        }

        private BSCStatus DoActionRecvRetAck(object param)
        {
            StopTimeoutRetry();
            for (int i = 0; i < SysConfig.DEV_NUM; i++)
            {
                if (_teamTestFinshFlags[i] && i + 1 == _lastReportTeamId)
                {
                    _teamTestFinshFlags[i] = false;
                    continue;
                }
            }
            PostEventAsync(BSCEvent.EVT_REPORT_MSG);
            return BSCStatus.ST_WORKING;
        }
        private BSCStatus DoActionRecvAlarmAck(object param)
        {
            int teamNo = int.Parse(param.ToString());
            StopTimeoutRetry();
            RemoveAlarmMsgForReprot(teamNo - 1);
            PostEventAsync(BSCEvent.EVT_REPORT_MSG);
            return BSCStatus.ST_WORKING;
        }

        private BSCStatus DoActionTeamReadyTimeout(object param)
        {
            AppendLogToUi("等待全部测试组就绪超时，进入部分就绪状态 ", LOG_TYPE.ERROR);
            return BSCStatus.ST_Ready;
        }

        private BSCStatus DoActionAllTeamReady(object param)
        {
            AppendLogToUi("所有测试组全部就绪", LOG_TYPE.DONE);
            StopTimeoutRetry();
            return BSCStatus.ST_Ready;
        }

        private BSCStatus DoActionServiceDestory(object param)
        {
            //   Hlog.E("DoActionServiceDestory disconnect with plc and stop all team test  wait poweroff @@@@@@@ NotImplemented");
            StopWorkTimerCount();
            for (int i = 0; i < _teamList.Count; i++)
            {
                _teamList[i].Destory();
            }
            SaveCurrentWorkData();
            TestRecord.Destory();
            DetailRecord.Destory();
            _overviewRecord.Destory();
            return BSCStatus.ST_STOP;
        }

        #endregion

        #region plc conn disconn
            private void ConnectPLCServer()
            {
                // (if fail it will auto retry in tcp mgr)

                //Hlog.E("DoActionConnectPLCServer start tcp connect and wait sharke hand");
                if (_viewModel.HandleServerConnState != ConnState.CONNECTED)
                {
                    // 固定监听本机所有网卡:64101（端口仍取配置）
                    bool startRet = _tcpClient.OpenServer("0.0.0.0", _tcpConfig.DestPort);
                    Hlog.I(Mod, startRet ? "start tcp main server success" : "start tcp main server failed");
                }
            }

            private void DisconnectPLCServer()
            {
                // (if fail it will auto retry in tcp mgr)

                //Hlog.E("DoActionConnectPLCServer start tcp connect and wait sharke hand");
                _tcpClient.CloseConn();
                Hlog.I(Mod, "connect plc server start");
            }
        #endregion

        #region TIMER BS
        private void RetryActionTimeout(int timerId)
        {
            if (timerId == _retryTimerId)
            {
                _retryTimerId = TimerTask.INVALID_TIMER_ID;
                PostEventAsync(_retryEvent);
            }
        }
        private void StartTimeoutRetry(int msecond, BSCEvent eventId)
        {
            _retryTimerId = _timerTask.StartTimer(msecond, false, RetryActionTimeout);
            _retryEvent = eventId;
            if (_retryTimerId == TimerTask.INVALID_TIMER_ID)
            {
                Hlog.E(Mod, "assign timer id failed");
            }
        }
        private void StopTimeoutRetry()
        {
            if (_timerTask != null)
            {
                if (_retryTimerId != TimerTask.INVALID_TIMER_ID)
                {
                    _timerTask.StopTimer(ref _retryTimerId);
                }
            }
        }

        private void StartWorkTimerCount()
        {
            _serverStartTime = DateTime.Now;
            _workTimerId = _timerTask.StartTimer(1000, true, WorkTimerCountTimeout);
            if (_workTimerId == TimerTask.INVALID_TIMER_ID)
            {
                Hlog.E(Mod, "assign timer id failed");
            }
        }

        private void StopWorkTimerCount()
        {
            if (_timerTask != null)
            {
                if (_workTimerId != TimerTask.INVALID_TIMER_ID)
                {
                    _timerTask.StopTimer(ref _workTimerId);
                }
            }
            _workHistoryTime += DateTime.Now - _serverStartTime;
        }

        private void WorkTimerCountTimeout(int timerId)
        {
            if (timerId == _workTimerId)
            {
                //_retryTimerId = TimerTask.INVALID_TIMER_ID;
                // PostEventAsync(_retryEvent);
                TimeSpan workTime = DateTime.Now - _serverStartTime;
                workTime += _workHistoryTime;
                _viewModel.WorkTime = Tools.TimeSpanToString(workTime);
            }
        }
        #endregion
        private void OnTcpConfigChange()
        {
            Hlog.W(Mod, "OnTcpConfigChange");
        }
        #region TCP BS

        private bool SendJsonResponse(string method, string status, object data)
        {
            byte[] ackByte = HCProtocol.EncodeJsonResponseBytes(method, status, data);
            Hlog.I(Mod, "report handler json ack:" + Encoding.UTF8.GetString(ackByte));
            // handler发起请求的应答：必须沿当前连接原路返回
            return SendToHandlerByOriginalChannel(ackByte);
        }
        private bool TryHandleJsonResponse(byte[] decodePackage, int packageLen)
        {
            byte[] candidate = new byte[packageLen];
            Array.Copy(decodePackage, candidate, packageLen);
            HCProtocol.JsonResponse response;
            string err = "";
            if (!HCProtocol.TryDecodeJsonResponse(candidate, out response, out err))
            {
                return false;
            }

            if (string.Equals(response.Status, "success", StringComparison.OrdinalIgnoreCase))
            {
                if (string.Equals(response.Method, HCProtocol.M_TEST_END, StringComparison.OrdinalIgnoreCase))
                {
                    if (_lastReportTeamId > 0)
                    {
                        AppendLogToUi("接收到机台测试上报JSON ACK", LOG_TYPE.WARNNING);
                        PostEventAsync(BSCEvent.EVT_RECV_RESULT_ACK, _lastReportTeamId);
                    }
                    return true;
                }
                if (string.Equals(response.Method, HCProtocol.M_ALARM, StringComparison.OrdinalIgnoreCase))
                {
                    AppendLogToUi("接收到向机台报警JSON ACK", LOG_TYPE.WARNNING);
                    PostEventAsync(BSCEvent.EVT_RECV_ALARM_ACK, _alarmSerial);
                    return true;
                }
            }
            else
            {
                AppendLogToUi($"接收到JSON响应失败:{response.Method}", LOG_TYPE.WARNNING);
                Hlog.W(Mod, $"json response failed method:{response.Method}");
                return true;
            }
            return false;
        }
        private bool TryParseJsonTestStart(object dataObj, ref int teamId, ref bool[] teamFlag)
        {
            if (!(dataObj is JObject data))
            {
                return false;
            }
            JToken bibToken;
            if (!data.TryGetValue("bibid", StringComparison.OrdinalIgnoreCase, out bibToken))
            {
                return false;
            }
            teamId = bibToken.Value<int>();
            teamFlag = new bool[BSTeamConfig.DUTS_COUNT];
            JToken sitesToken;
            if (!data.TryGetValue("sites", StringComparison.OrdinalIgnoreCase, out sitesToken))
            {
                return false;
            }
            JArray sites = sitesToken as JArray;
            if (sites == null)
            {
                return false;
            }
            foreach (JObject site in sites.OfType<JObject>())
            {
                int siteId = site.Value<int?>("siteid") ?? 0;
                bool enable = site.Value<bool?>("IsEnable") ?? false;
                int idx = siteId - 1;
                if (idx >= 0 && idx < teamFlag.Length)
                {
                    teamFlag[idx] = enable;
                }
            }
            return true;
        }

        private bool TryHandleJsonRequest(byte[] decodePackage, int packageLen)
        {
            byte[] candidate = new byte[packageLen];
            Array.Copy(decodePackage, candidate, packageLen);
            HCProtocol.JsonRequest request;
            string err = "";
            if (!HCProtocol.TryDecodeJsonRequest(candidate, out request, out err))
            {
                return false;
            }

            string method = request.Method?.ToLowerInvariant() ?? "";
            if (method == HCProtocol.M_GET_VERSION)
            {
                string version = typeof(BSController).Assembly.GetName().Version?.ToString() ?? "1.0.0.0";
                SendJsonResponse(request.Method, "success", new { version });
                return true;
            }
            if (method == HCProtocol.M_LOT_START || method == HCProtocol.M_LOT_END || method == HCProtocol.M_SWITCH)
            {
                SendJsonResponse(request.Method, "success", new { });
                return true;
            }
            if (method == HCProtocol.M_SET_MACHINE_ACTION)
            {
                SendJsonResponse(request.Method, "success", new { });
                return true;
            }
            if (method == HCProtocol.M_GET_MACHINE_ACTION)
            {
                JObject dataObj = request.Data as JObject;
                int bibId = dataObj?.Value<int?>("bibid") ?? 0;
                SendJsonResponse(request.Method, "success", new { bibid = bibId, actionstatus = true });
                return true;
            }
            if (method == HCProtocol.M_TEST_START)
            {
                int teamId = 0;
                bool[] teamFlag = new bool[BSTeamConfig.DUTS_COUNT];
                if (!_viewModel.ServiceStart)
                {
                    SendJsonResponse(request.Method, "fail", new { reason = "service not started" });
                    return true;
                }
                if (!TryParseJsonTestStart(request.Data, ref teamId, ref teamFlag) || teamId <= 0 || teamId > _teamList.Count)
                {
                    SendJsonResponse(request.Method, "fail", new { reason = "invalid teststart payload" });
                    return true;
                }
                int validCount = teamFlag.Count(v => v);
                if (validCount == 0)
                {
                    SendJsonResponse(request.Method, "fail", new { reason = "no enabled site" });
                    return true;
                }
                bool ret = _teamList[teamId - 1].ExcuteTestTask(teamFlag);
                if (ret)
                {
                    SendJsonResponse(request.Method, "success", new { });
                    if (!_recordStart)
                    {
                        _recordStart = true;
                        _startWorkTime = DateTime.Now;
                    }
                }
                else
                {
                    SendJsonResponse(request.Method, "fail", new { reason = "execute failed" });
                }
                return true;
            }
            SendJsonResponse(request.Method, "fail", new { reason = "unsupported method" });
            return true;
        }
        
        public bool OnTCPRecvDataHandle(byte[] data)
        {
            return HandleTCPData(data, _decodeDataBuf, ref _recvLeftLen, "main");
        }
        private bool HandleTCPData(byte[] data, byte[] decodeBuffer, ref int recvLeftLen, string channelTag)
        {
            if (recvLeftLen + data.Length > BUF_SIZE)
            {
                Array.Clear(decodeBuffer, 0, BUF_SIZE);
                Array.Copy(data, decodeBuffer, data.Length);
                recvLeftLen = data.Length;
            }
            else
            {
                Array.Copy(data, 0, decodeBuffer, recvLeftLen, data.Length);
                recvLeftLen += data.Length;
            }
            Hlog.I(Mod, $"RECV TCP MSG[{channelTag}]:" + Encoding.Default.GetString(data));
            byte[] decodePackage = decodeBuffer;
            int packageLen = recvLeftLen;
            if (TryHandleJsonResponse(decodePackage, packageLen) || TryHandleJsonRequest(decodePackage, packageLen))
            {
                Array.Clear(decodeBuffer, 0, BUF_SIZE);
                recvLeftLen = 0;
                return true;
            }
            string pending = Encoding.UTF8.GetString(decodeBuffer, 0, packageLen).Trim();
            if (pending.StartsWith("{") && !pending.EndsWith("}"))
            {
                return true;
            }
            AppendLogToUi($"接收到无效JSON指令[{channelTag}]:" + pending, LOG_TYPE.WARNNING);
            Array.Clear(decodeBuffer, 0, BUF_SIZE);
            recvLeftLen = 0;
            return true;
        }

        private void OnTCPConnectChange(bool isConnect)
        {
            if (isConnect)
            {
                _viewModel.HandleServerConnState = ConnState.CONNECTED;
                AppendLogToUi("机台连接成功", LOG_TYPE.DONE);
                EnsureTxChannelConnected();
            }
            else
            {
                _viewModel.HandleServerConnState = ConnState.DISCONNECT;
                AppendLogToUi("机台连接断开", LOG_TYPE.ERROR);
            }
        }

        private bool OnTxRecvDataHandle(byte[] data)
        {
            // 主动上报通道默认不处理下行数据
            return true;
        }

        private void OnTxConnectChange(bool isConnect)
        {
            Hlog.I(Mod, isConnect ? "tx channel connected" : "tx channel disconnected");
        }
        #endregion



        private void SendTestFinshReporReq(int teamId)
        {
            if (CurState == BSCStatus.ST_WORKING)
            {
                _teamTestFinshFlags[teamId] = true;
                PostEventAsync(BSCEvent.EVT_REPORT_MSG);
            }
            _stopWorkTime = DateTime.Now;
        }

        private void SaveCurrentWorkData()
        {
            if (_recordStart)
            {
                TimeSpan workTime = _stopWorkTime - _startWorkTime;
                CSVRecord record = _overviewRecord.GetRecordObject();
                if (record != null)
                {
                    //Start,Duration,Material,Order,WorkOrder,Bin1,Bin2,Bin3,Bin4,Total,Bin1Precent,Temp,Config
                    uint recordId = record.StartOneRecord();
                    float bin1Precent = (float)(_binRecord[0] * 100) / (float)_viewModel.TestDutNum;
                    record.AddFixedRecord(recordId, _startWorkTime.ToString("yyyy-MM-dd HH:mm:ss"));
                    record.AddFixedRecord(recordId, Tools.TimeSpanToString(workTime));
                    record.AddFixedRecord(recordId, SysConfig.MaterialNo);
                    record.AddFixedRecord(recordId, SysConfig.OrderNo);
                    record.AddFixedRecord(recordId, SysConfig.WorkOrderNo);
                    record.AddFixedRecord(recordId, _binRecord[0]);
                    record.AddFixedRecord(recordId, _binRecord[1]);
                    record.AddFixedRecord(recordId, _binRecord[2]);
                    record.AddFixedRecord(recordId, _binRecord[3]);
                    record.AddFixedRecord(recordId, _viewModel.TestDutNum);
                    record.AddFixedRecord(recordId, bin1Precent);
                    record.AddFixedRecord(recordId, SysConfig.WorkStageName);
                    if (SysConfig.TempState == (byte)TempState.TmpHight)
                    {
                        record.AddFixedRecord(recordId, _bsConfig.HightTempValue);
                    }
                    else if (SysConfig.TempState == (byte)TempState.TmpMixture)
                    {
                        record.AddFixedRecord(recordId, $"{_bsConfig.HightTempValue}-N");
                    }
                    else
                    {
                        record.AddFixedRecord(recordId, "N");
                    }
                    record.AddFixedRecord(recordId, _viewModel.PolicyName);

                    PolicyManager policyMgr = PolicyManager.Instance;
                    int stageNum = policyMgr.Policy.MemberList.Count;
                    record.AddFixedRecord(recordId, stageNum);
                    for (int i = 0; i < stageNum; i++)
                    {
                        record.AddOneRecord(recordId, policyMgr.Policy.MemberList[i].param.CfgFileName);
                        string tempState = policyMgr.Policy.MemberList[i].param.TempFlag == (byte)TempState.TmpHight ? "H" : "N";
                        string param = $"E/T/E/R/O {tempState}/{policyMgr.Policy.MemberList[i].param.TimeoutMinute}/{policyMgr.Policy.MemberList[i].param.ExcuteFrequency}/{policyMgr.Policy.MemberList[i].param.RepeatMaxFail}/{policyMgr.Policy.MemberList[i].param.RepeatOptimization}";
                        record.AddOneRecord(recordId, param);
                        record.AddOneRecord(recordId, _stateFailStatistics[i]);
                    }
                    record.SaveRecord(recordId, true);
                }
            }

        }

        private void LoadPolicyFile()
        {
            string errorMsg = "";
            PolicyFile testPolicy;
            if (SysConfig.WorkMode == WorkMode.Slave)
            {
                testPolicy = PolicyFile.Deserialize(_sysConfig.TestPolicyPath, ref errorMsg);
            }
            else
            {
                testPolicy = PolicyFile.Deserialize(SysConfig.GetPolicyFileFullPath(_sysConfig.TestPolicyPath), ref errorMsg);
            }
            if (testPolicy == null)
            {
                AppendLogToUi("读取测试方案失败:" + errorMsg, LOG_TYPE.ERROR);
                _viewModel.PolicyName = "";
                PolicyManager.Instance.LoadPolicy(null);
                return;
            }
            if (_stateFailStatistics == null || _stateFailStatistics.Length < testPolicy.MemberList.Count)
            {
                _stateFailStatistics = new UInt32[testPolicy.MemberList.Count];
            }
            _viewModel.PolicyName = _sysConfig.TestPolicyPath;
            AppendLogToUi("读取测试方案成功", LOG_TYPE.DONE);
            PolicyManager.Instance.LoadPolicy(testPolicy);
            Hlog.I(Mod, "test config:" + _viewModel.PolicyName);
        }
    }

}
