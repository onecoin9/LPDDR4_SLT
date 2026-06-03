using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading.Tasks;
using Hsg.BLL.config;
using Hsg.BLL.Net;
using Hsg.Common;
using Hsg.BLL.Model;

namespace Hsg.BLL
{
    /// <summary>
    /// 内部事务，外部不要调用。
    /// </summary>
    public enum DutEvent_I
    {
        /// <summary>
        /// 新状态初始化
        /// </summary>
        EVT_INIT,
        ///// <summary>
        ///// 启动连接
        ///// </summary>
        //EVT_START_CONN,
        ///// <summary>
        ///// 关闭连接
        ///// </summary>
        EVT_CLOSE_CONN,
        /// <summary>
        /// udp 创建连接失败
        /// </summary>
        EVT_CONN_FAIL,
        /// <summary>
        /// 重试连接
        /// </summary>
        EVT_CONN_RETRY,
        /// <summary>
        /// 收到上层指令，开始执行一个测试请求
        /// </summary>
        EVT_EXCUTE_TEST,
        /// <summary>
        /// 收到 测试板准备就绪,开始进入测试
        /// </summary>
        EVT_SLAVE_READY,
        /// <summary>
        /// 发送开始指令附带配置信息
        /// </summary>
        EVT_SND_CONFIG,
        /// <summary>
        /// 接收到启动ACK
        /// </summary>
        EVT_SLAVE_START_ACK,
        /// <summary>
        /// 收到测试中的信息（容量，rank,die）
        /// </summary>
        EVT_SLAVE_TEST_INFO,
        /// <summary>
        /// 接收执行命令(执行中的命令,如 0x11,0x12,0x13)
        /// </summary>
        EVT_SLAVE_EXEC_CMD,
        /// <summary>
        /// 收到测试结束
        /// </summary>
        EVT_SLAVE_TEST_OK,
        /// <summary>
        /// 收到测试失败1
        /// </summary>
        EVT_SLAVE_TEST_FAIL1,
        /// <summary>
        /// 收到测试失败2
        /// </summary>
        EVT_SLAVE_TEST_FAIL2,
        /// <summary>
        /// 收到测试超时
        /// </summary>
        EVT_SLAVE_TEST_TIMEOUT,
        /// <summary>
        /// 取消测试任务
        /// </summary>
        EVT_CANCEL_TASK,
        /// <summary>
        /// 从测试结束恢复到初始状态
        /// </summary>
        EVT_RESET_STATUS,
        /// <summary>
        /// 测试前，或者测试中，温度异常
        /// </summary>
        EVT_TEMP_ASSERT,
        /// <summary>
        /// 测试完成保存记录
        /// </summary>
        EVT_SAVE_RESULT,
        /// <summary>
        /// 退出
        /// </summary>
        EVT_DESTORY
    }

    public enum DutEvent_E
    {
        DUT_EVT_SET_PWR_KEY,
    }
    public enum DutStatus
    {
        /// <summary>
        /// 初始状态
        /// </summary>
        ST_INIT,
        /// <summary>
        /// 启动连接,检查授权
        /// </summary>
       // ST_CONNECTING,
        /// <summary>
        /// 通讯和授权正常，进入就绪状态,等待进入测试
        /// </summary>
        ST_READY,
        /// <summary>
        /// 收到开始测试命令，等待测试板Ready
        /// </summary>
        ST_WAIT_BEGING,
        ///// <summary>
        ///// 给对应测试板上电
        ///// </summary>
        //ST_TEST_POWER_UP,
        /// <summary>
        ///// 等待测试板Ready
        ///// </summary>
        //ST_TEST_WAIT_ACK,
        /// <summary>
        /// 发送开始测试
        /// </summary>
        ST_TEST_START,
        /// <summary>
        /// 因为各种失败，或者测试完成，最后到达测试结束。
        /// </summary>
        ST_TEST_END,
    }

    public class StateCode
    {
        public const ushort SCODE_FUN_FAIL = 0xFFFF;//  测试失败
        public const byte SCODE_INVALID = 0xFF; // 无效
        public const byte SCODE_DUT_REBOOT = 0xFE; // 监测到重启
        public const byte SCODE_DUT_CONN_TIMEOUT = 0xFD; // 监测到连接超时
        public const byte SCODE_RUNIN_FAILE = 0xFC; // 外部触发失败，（老化测试日志监测到失败）
        public const byte SCODE_TB_COMMUNICATE_ERROR = 0xFB;// 通讯板通讯超时
        public const byte SCODE_TEMP_ERROR = 0xFA;// 温度不达标
        public const byte SCODE_TEMP_MAIN_ERROR = 0xF9;// 温度主板异常（dut 状态）
        public const byte SCODE_TEMP_FUN_ERROR = 0xF8;// 风扇异常
        public const byte SCODE_TEMP_CONNECT_ERROR = 0xF7;// 通讯异常（温控总板状态）
        public const byte SCODE_RESERVE_MIN = 0xF0; // 预留最小状态码
        public const byte SCODE_OK = 0;
    }

    public delegate void IOnDutStageChange(int dutId, TestStage stage);
    public delegate void IOnDutPostEventAsync(DutEvent_E evt, int instanceId);
    public partial class DutMaster : StateMechine<DutStatus, DutEvent_I>
    {
        private UdpSender _dutSender;
        public UdpSenderConfig _senderConfig;
        public static readonly byte ERR_CODE_INALID = 0x00;
        public static readonly byte ERR_CODE_OK = 0x02;

        public static readonly byte ERR_CODE_TIMEOUT = 0x06;
        public static readonly byte ERR_CODE_FAIL1 = 0x03;//成功有瑕疵,目前主要是表示大电流
        public static readonly byte ERR_CODE_FAIL2 = 0x07;
        public static readonly byte ERR_CODE_CANCEL = 0x08;
        public static readonly byte ERR_CODE_TEMP_BAD = 0x05;// 温控异常
        public static readonly byte ERR_OTHER_ENV_BAD = 0x09; // 其他环境异常

        private int _teamIndex = 0;
        private TimerTask _timerTask;
        private DutEvent_I _retryEvent;
        private int _retryTimerId = TimerTask.INVALID_TIMER_ID;
        private TestStage _testStage = TestStage.ST_READY;
        private float _testTemp;
        public TestStage TestStage
        {
            get { return _testStage; }
            private set
            {
                if (_testStage != value)
                {
                    _testStage = value;
                    if (_onStageChange != null)
                    {
                        _onStageChange(_instanceId, _testStage);
                    }
                }
            }
        }
        private byte _errCode;
        private IOnDutStageChange _onStageChange;
        private IOnDutPostEventAsync _onDutPostEventAsync;
        private DateTime _startTime;
        private TimeSpan _testTime;//测试用的时间（从收到准备就绪开始）
        private bool _bTestStart = false; // 标记是否收到准备就绪，开始测试
        private bool _bRecvDetailInfo = false;// 标记是否收到容量信息，避免重复接收和记录
        private BinCodeManager _binCodeManager;
        private StringBuilder _detailBuilder;
        public DutMaster(int teamIndex, int groupId, int instanceId, StringBuilder detailBuilder, IOnDutStageChange onStageChange, IOnDutPostEventAsync onDutPostEventAsync) : base("DutMaster" + (teamIndex + 1).ToString() + "-" + (groupId + 1).ToString() + "-" + (instanceId + 1).ToString())
        {
            _dutSender = new UdpSender();
            _senderConfig = new UdpSenderConfig(teamIndex, groupId, instanceId, OnConfigChange);
            _instanceId = instanceId;
            _groupId = groupId;
            _teamIndex = teamIndex;
            _detailBuilder = detailBuilder;
            _timerTask = TimerTask.GetTimerTaskInstance();
            _onStageChange += onStageChange;
            _onDutPostEventAsync = onDutPostEventAsync;
            _errCode = ERR_CODE_INALID;
            _dutRecordLastId = -1;
            _teamStartTimestamp = 0;
            _lastCmd = 0;
            _testInfoCSV = BSController.DetailRecord.GetRecordObject();
            _recordInstance = _testInfoCSV.StartOneRecord();
            _testTime = new TimeSpan(0);
            powerSet = new PowerSet();
            _binCodeManager = BinCodeManager.GetInstance();
            RegisterEventAction();
        }
        private void RegisterEventAction()
        {
            // RegisterStateHandle(DutStatus.ST_INIT, DutEvent_I.EVT_INIT, DoActionFirstInit);
            //  RegisterStateHandle(DutStatus.ST_INIT, DutEvent_I.EVT_START_CONN, DoActionStartConn);

            // RegisterStateHandle(DutStatus.ST_CONNECTING, DutEvent_I.EVT_INIT, DoActionStartConn);
            // RegisterStateHandle(DutStatus.ST_CONNECTING, DutEvent_I.EVT_CONN_RETRY, DoActionStartConn);
            //RegisterStateHandle(DutStatus.ST_CONNECTING, DutEvent_I.EVT_CONN_FAIL, DoActionConnectFailed);

            RegisterStateHandle(DutStatus.ST_READY, DutEvent_I.EVT_EXCUTE_TEST, DoActionExcuteTest);
            // RegisterStateHandle(DutStatus.ST_READY, DutEvent_I.EVT_CLOSE_CONN, DoActionCloseConn);
            //RegisterStateHandle(DutStatus.ST_READY, DutEvent_I.EVT_CANCEL_TASK, DoActionCancelConn);
            RegisterStateHandle(DutStatus.ST_WAIT_BEGING, DutEvent_I.EVT_SLAVE_READY, DoActionRecvDutReady);
            RegisterStateHandle(DutStatus.ST_WAIT_BEGING, DutEvent_I.EVT_SLAVE_TEST_TIMEOUT, DoActionSlaveTimeout);
            RegisterStateHandle(DutStatus.ST_WAIT_BEGING, DutEvent_I.EVT_CANCEL_TASK, DoActionCancelConn);
            RegisterStateHandle(DutStatus.ST_WAIT_BEGING, DutEvent_I.EVT_TEMP_ASSERT, DoActionTempAssert);

            RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_INIT, DoActionTestStart);
            RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_SND_CONFIG, DoActionSendStartConfig);
            RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_SLAVE_READY, DoActionRecvDutRebootReady);
            RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_SLAVE_START_ACK, DoActionRecvStartAck);
            RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_SLAVE_EXEC_CMD, DoActionRecvOtherCmd);
            RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_SLAVE_TEST_TIMEOUT, DoActionSlaveTimeout);
            RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_SLAVE_TEST_OK, DoActionRecvDutTestSuccess);
            RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_SLAVE_TEST_FAIL1, DoActionRecvDutTestFailed1);
            RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_SLAVE_TEST_FAIL2, DoActionRecvDutTestFailed2);
            RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_SLAVE_TEST_INFO, DoActionRecvTestInfor);
            //RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_CLOSE_CONN, DoActionCloseConn);
            RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_CANCEL_TASK, DoActionCancelConn);
            RegisterStateHandle(DutStatus.ST_TEST_START, DutEvent_I.EVT_TEMP_ASSERT, DoActionTempAssert);


            RegisterStateHandle(DutStatus.ST_TEST_END, DutEvent_I.EVT_INIT, DoActionTestEnd);
            RegisterStateHandle(DutStatus.ST_TEST_END, DutEvent_I.EVT_SAVE_RESULT, DoActionSaveResult);

            // RegisterStateHandle(DutStatus.ST_TEST_END, DutEvent_I.EVT_CLOSE_CONN, DoActionCloseConn);
            RegisterStateHandle(DutStatus.ST_TEST_END, DutEvent_I.EVT_EXCUTE_TEST, DoActionExcuteTest);
            RegisterStateHandle(DutStatus.ST_TEST_END, DutEvent_I.EVT_RESET_STATUS, DoActionBackToReady);           
        }
        protected override void NotifyStateChange(DutStatus state)
        {
            switch (state)
            {
                //case DutStatus.ST_INIT:
                //    _errCode = ERR_CODE_INALID;
                //    this.TestStage = TestStage.ST_NOT_START;
                //    PostEventAsync(DutEvent_I.EVT_INIT);
                //    break;
                //case DutStatus.ST_CONNECTING:
                //    _testStage = TestStage.ST_PREPARE;
                //   break;
                case DutStatus.ST_READY:
                    _errCode = ERR_CODE_INALID;
                    //this.TestStage = TestStage.ST_PREPARE;
                    this.TestStage = TestStage.ST_READY;
                    break;
                case DutStatus.ST_WAIT_BEGING:
                    this.TestStage = TestStage.ST_TESTING;
                    break;
                //
                case DutStatus.ST_TEST_START:
                    this.TestStage = TestStage.ST_TESTING;
                    PostEventAsync(DutEvent_I.EVT_INIT);
                    break;
                case DutStatus.ST_TEST_END:
                    if (_bTestStart)
                    {
                        _testTime = DateTime.Now - _startTime;
                        _bRecvDetailInfo = false;
                    }
                    else
                    {
                        _testTime = new TimeSpan(0);
                    }

                    AddStageDetail("测试结束:" + GetTestTime());
                    if (_errCode == ERR_CODE_OK)
                    {
                        this.TestStage = TestStage.ST_TEST_SUCCESS;
                    }
                    else if (_errCode == ERR_CODE_FAIL1 || _errCode == ERR_CODE_FAIL2)
                    {
                        this.TestStage = TestStage.ST_TEST_FAIL;
                    }
                    else
                    {
                        this.TestStage = TestStage.ST_TEST_TIMEOUT;
                    }
                    PostEventAsync(DutEvent_I.EVT_INIT);
                    break;
            }
        }
        #region do event action
        private DutStatus DoActionFirstInit(object param)
        {
            //Hlog.E(" not impliment @@@@ DoActionFirstInit");
            //uiState.ResetStageDetail();
            return DutStatus.ST_READY;
            //  return DutStatus.ST_CONNECTING;
        }

        private DutStatus DoActionStartConn(object param)
        {
            //Hlog.E("@@@@ DoActionStartConn");
            return DutStatus.ST_READY;
        }

        private DutStatus DoActionCancelConn(object param)
        {
            //Hlog.E("@@@@ DoActionStartConn");
            StopTimeoutRetry();
            _errCode = ERR_CODE_CANCEL;

            _statusCode = StateCode.SCODE_INVALID;
            AddStageDetail("测试取消:" + _statusCode.ToString("X2"));
            return DutStatus.ST_TEST_END;
        }
        private DutStatus DoActionRecvTestInfor(object param)
        {
            //Hlog.E("@@@@ DoActionStartConn");
            if (_bRecvDetailInfo)
            {
                return DutStatus.ST_TEST_START;
            }
            _bRecvDetailInfo = true;
            AddStageDetail(_testInfor);
            return DutStatus.ST_TEST_START;
        }

        private DutStatus DoActionTestEnd(object param)
        {
            byte binCode = _binCodeManager.DefaultBin;
            //  _binCodeManager.GetBinNumber(_errCode, ref binCode);
            _testInfoCSV.AddFixedRecord(_recordInstance, GetTestTime());
            _testInfoCSV.AddFixedRecord(_recordInstance, "team" + (_teamIndex + 1).ToString());
            _testInfoCSV.AddFixedRecord(_recordInstance, "board" + (_groupId + 1).ToString());
            _testInfoCSV.AddFixedRecord(_recordInstance, "dut" + (_instanceId + 1).ToString());

            _testInfoCSV.AddFixedRecord(_recordInstance, _testBoardSW);
            
            _testInfoCSV.AddFixedRecord(_recordInstance, _testTemp.ToString());
            string resultDescription = GetResultDescript(_errCode);
            _testInfoCSV.AddFixedRecord(_recordInstance, _errCode);
            _testInfoCSV.AddFixedRecord(_recordInstance, resultDescription);
            _testInfoCSV.AddFixedRecord(_recordInstance, _statusCode.ToString("X2"));
            _testInfoCSV.AddFixedRecord(_recordInstance, ParseStateCodeMsg(_statusCode));
            
            _testInfoCSV.AddFixedRecord(_recordInstance, _stageInfo);
            _testInfoCSV.AddFixedRecord(_recordInstance, _repeatInfo);
            //Hlog.E("@@@@ DoActionStartConn");
            return DutStatus.ST_TEST_END;
        }
        public static string GetResultDescript(byte errorCode)
        {
            if (errorCode == ERR_CODE_FAIL2 || errorCode == ERR_CODE_FAIL1)
            {
                return "fail";
            }
            else if (errorCode == ERR_CODE_OK)
            {
                return "pass";
            }
            else if (errorCode == ERR_CODE_TIMEOUT)
            {
                return "timeout";
            }
            else if (errorCode == ERR_CODE_CANCEL)
            {
                // _testInfoCSV.AddFixedRecord(_recordInstance, "取消:"+ _statusCode.ToString("X2"));
                return "cancel";
            }
            else
            {
                return "other";
            }
        }
        private DutStatus DoActionSaveResult(object param)
        {
            _testInfoCSV.SaveRecord(_recordInstance, false);
            return DutStatus.ST_TEST_END;
        }

        private DutStatus DoActionCancelTask(object param)
        {
            //Hlog.E("@@@@ DoActionStartConn");
            StopTimeoutRetry();
            return DutStatus.ST_INIT;
        }

        private DutStatus DoActionTempAssert(object param)
        {
            float assertTemp = 0;
            if (param != null)
            {
                float.TryParse(param.ToString(), out assertTemp);
                _testTemp = assertTemp;
            }
            _errCode = ERR_CODE_TEMP_BAD;
            if (_teampCtrMainBoardError)
            {
                _statusCode = StateCode.SCODE_TEMP_MAIN_ERROR;
            }
            else
            {
                _statusCode = StateCode.SCODE_TEMP_ERROR;
            }

            StopTimeoutRetry();
            AddStageDetail("温度异常:" + assertTemp.ToString());
            return DutStatus.ST_TEST_END;
        }
        private DutStatus DoActionExcuteTest(object param)
        {
            //Hlog.E(" @@@@ DoActionExcuteTest");
            bool teampReady = Convert.ToBoolean(param);
            _testInfor = "";
            _lastCmd = 0;
            _statusCode = StateCode.SCODE_INVALID;
            _dutRecordLastId = -1;
            _bTestStart = false;
            _errCode = ERR_CODE_INALID;
            _testBoardSW = "None";

            _testInfoCSV.ClearRecordBuf(_recordInstance);//  清除无效的记录
            _testInfoCSV.AddFixedRecord(_recordInstance, _taskSerialNo);
            _testInfoCSV.AddFixedRecord(_recordInstance, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            _testInfoCSV.AddFixedRecord(_recordInstance, _teamStartTimestamp.ToString());
           

            ResetStageDetail();
            AddStageDetail("开始测试:" + _stageInfo + "-" + _repeatInfo);
            if (teampReady)
            {
                AddStageDetail("进入测试，等待测试板开机");
            }
            else // 温度异常
            {
                PostEventAsync(DutEvent_I.EVT_TEMP_ASSERT);
            }

            return DutStatus.ST_WAIT_BEGING;
        }


        private DutStatus DoActionBackToReady(object param)
        {
            //Hlog.E(" @@@@ DoActionExcuteTest");
            return DutStatus.ST_READY;
        }

        private DutStatus DoActionRecvDutReady(object param)
        {
            //Hlog.E("@@@@ DoActionRecvDutReady");
            StopTimeoutRetry();
            //_bTestStart = false;
            _bRecvDetailInfo = false;
            //AppendLogToUi("测试板准备就绪", LOG_TYPE.DONE);

            return DutStatus.ST_TEST_START;
        }

        private DutStatus DoActionTestStart(object param)
        {
            _startTime = DateTime.Now;
            _bTestStart = true;
            _bRecvDetailInfo = false;


            PostEventAsync(DutEvent_I.EVT_SND_CONFIG);
            AddStageDetail("测试板已开机");
            AddStageDetail("开始传输测试参数");
            //AppendLogToUi("开始传输测试参数", LOG_TYPE.INFO);

            return DutStatus.ST_TEST_START;
        }
        private DutStatus DoActionSendStartConfig(object param)
        {
            byte[] sendData = DutProtocol.GenerateStartTestPackage(_testBoardCfg.ConfigBytes);
            IPEndPoint point = new IPEndPoint(IPAddress.Parse(_senderConfig.IP), UInt16.Parse(_senderConfig.TxPort));
            _dutSender.SendData(sendData, point);
            StartRetryTimer(5000, DutEvent_I.EVT_SND_CONFIG);
            return DutStatus.ST_TEST_START;
        }

        private DutStatus DoActionRecvStartAck(object param)
        {
            //Hlog.E("@@@@ DoActionRecvStartAck");
            AddStageDetail("测试板收到参数开始执行");
            StopTimeoutRetry();
            if (SystemStatus.DebugBoardTest)
            {
                _errCode = ERR_CODE_OK;
                _statusCode = StateCode.SCODE_OK;
                return DutStatus.ST_TEST_END;
            }
            return DutStatus.ST_TEST_START;
        }
        private DutStatus DoActionRecvOtherCmd(object param)
        {
            //Hlog.E("@@@@ DoActionRecvStartAck");
            StopTimeoutRetry();
            if (SystemStatus.DebugBoardTest)
            {
                _errCode = ERR_CODE_OK;
                _statusCode = StateCode.SCODE_OK;
                return DutStatus.ST_TEST_END;
            }
            return DutStatus.ST_TEST_START;
        }

        private DutStatus DoActionSlaveTimeout(object param)
        {
            StopTimeoutRetry();
            _errCode = ERR_CODE_TIMEOUT;
            if (param == null || !ushort.TryParse(param.ToString(), out _statusCode))
            {
                _statusCode = 0;
            }
            if (_statusCode == StateCode.SCODE_DUT_CONN_TIMEOUT)
            {
                AddStageDetail("测试板启动超时");
            }
            else if (_statusCode == StateCode.SCODE_TB_COMMUNICATE_ERROR)
            {
                AddStageDetail("通讯板通讯超时");
            }
            else
            {
                AddStageDetail("测试总时长超出");
            }
            return DutStatus.ST_TEST_END;
        }

        private DutStatus DoActionRecvDutTestSuccess(object param)
        {
            // Hlog.E(" not impliment @@@@ DoActionRecvDutTestSuccess");
            _errCode = ERR_CODE_OK;
            AddStageDetail("测试成功:0x" + _statusCode.ToString("X2"));
            //AppendLogToUi("测试成功", LOG_TYPE.DONE);
            return DutStatus.ST_TEST_END;
        }

        private DutStatus DoActionRecvDutTestFailed1(object param)
        {
            //Hlog.E(" not impliment @@@@ DoActionRecvDutTestFailed1");
            _errCode = ERR_CODE_FAIL1;
            AddStageDetail("测试失败:0x" + _statusCode.ToString("X2"));
            //AppendLogToUi("测试失败", LOG_TYPE.ERROR);
            return DutStatus.ST_TEST_END;
        }

        private DutStatus DoActionRecvDutTestFailed2(object param)
        {
            //Hlog.E(" not impliment @@@@ DoActionRecvDutTestFailed1");
            byte abnormalCode = (byte)(_statusCode & 0xFF);
            if (_binCodeManager.CheckAbnormalErrorCode(abnormalCode))
            {
                _errCode = ERR_OTHER_ENV_BAD;
            }
            else
            {
                _errCode = ERR_CODE_FAIL2;
            }
            AddStageDetail("测试失败:0x" + _statusCode.ToString("X2"));
            //AppendLogToUi("测试失败", LOG_TYPE.ERROR);
            return DutStatus.ST_TEST_END;
        }
        private DutStatus DoActionRecvDutRebootReady(object param)
        {
            //Hlog.E("@@@@ DoActionRecvDutReady");
            _errCode = ERR_CODE_FAIL2;
            _statusCode = StateCode.SCODE_DUT_REBOOT;
            AddStageDetail("测试板重启");
            AppendLogToUi("测试板重启", LOG_TYPE.ERROR);
            return DutStatus.ST_TEST_END;
        }
        #endregion

        #region timer task
        private void StartRetryTimer(int msecond, DutEvent_I eventId)
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
            if (_retryTimerId != TimerTask.INVALID_TIMER_ID)
            {
                _timerTask.StopTimer(ref _retryTimerId);
            }
        }

        private void RetryActionTimeout(int timerId)
        {
            if (timerId == _retryTimerId)
            {
                _retryTimerId = TimerTask.INVALID_TIMER_ID;
                PostEventAsync(_retryEvent);
            }
        }
        #endregion

        public static string ParseStateCodeMsg(ushort stateCode)
        {
            switch (stateCode)
            {
                case StateCode.SCODE_FUN_FAIL:
                    return "Timeout/Fail";
                case StateCode.SCODE_DUT_REBOOT:
                    return "TestBoradReboot";
                case StateCode.SCODE_DUT_CONN_TIMEOUT:
                    return "TestBoardConnTimeout";
                case StateCode.SCODE_RUNIN_FAILE:
                    return "Outside";
                case StateCode.SCODE_TB_COMMUNICATE_ERROR:
                    return "CommunicateBoardError";
                case StateCode.SCODE_TEMP_ERROR:
                    return "TempError";
                case StateCode.SCODE_TEMP_MAIN_ERROR:
                    return "TempCtrlError";
                case StateCode.SCODE_TEMP_FUN_ERROR:
                    return "FanError";
                case StateCode.SCODE_TEMP_CONNECT_ERROR:
                    return "TempCtrConnError";
            }
            return "--";
        }
        public static bool CheckStateCodeAbnormal(ushort stateCode, ref ushort abnormalCode)
        {
            switch (stateCode)
            {
                case StateCode.SCODE_DUT_REBOOT:
                case StateCode.SCODE_DUT_CONN_TIMEOUT:
                case StateCode.SCODE_RUNIN_FAILE:
                case StateCode.SCODE_TB_COMMUNICATE_ERROR:
                case StateCode.SCODE_TEMP_ERROR:
                case StateCode.SCODE_TEMP_MAIN_ERROR:
                    abnormalCode = stateCode;
                    return true;
                case StateCode.SCODE_INVALID:
                    return false;
                default:
                    abnormalCode = 0;
                    return true;
            }
        }


        public static bool FoundMainBoradState(ushort stateCode)
        {
            if (stateCode == StateCode.SCODE_TB_COMMUNICATE_ERROR || stateCode == StateCode.SCODE_TEMP_MAIN_ERROR)
                return true;
            return false;
        }
        /// <summary>
        /// 检查环境异常的状态码【温度，通信板通讯】
        /// </summary>
        /// <param name="stateCode"></param>
        /// <returns></returns>
        public static bool FoundEnvoriementAbnormalCode(ushort stateCode)
        {
            if (/*stateCode == StateCode.SCODE_TB_COMMUNICATE_ERROR */
                // || stateCode == StateCode.SCODE_TEMP_MAIN_ERROR
                 stateCode == StateCode.SCODE_TEMP_CONNECT_ERROR
                || stateCode == StateCode.SCODE_TEMP_FUN_ERROR
                || stateCode == StateCode.SCODE_TEMP_ERROR)
                return true;
            return false;
        }
    }

}
