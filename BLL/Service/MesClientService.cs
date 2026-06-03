using Hsg.BLL.config;
using Hsg.BLL.Model;
using Hsg.BLL.Net;
using Hsg.Common;
using Hsg.Common.ADO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
namespace Hsg.BLL.Service
{
    internal class StateReport
    {
        public string cmd;
        public int stateCode;
        public string detail;
        public const int STATE_CODE_OK = 0;
        public const int STATE_CODE_LAUNCH = 1;
        public const int STATE_CODE_OTHER = 2;
    }

    internal class TsConfig : SlaveModeConfig
    {
        public string TSName;
    }
    internal class ConfigResponse
    {
        public string cmd;
        public TsConfig config;
    }
    internal class WorkStateAck
    {
        public string cmd;
        public int stateCode;
    }
    internal class ExitAck
    {
        public string cmd;
        public int stateCode;
        public string detail;
    }
    internal class BoxCheckAck
    {
        public string cmd;
        public int stateCode;
        public ushort[] memberStatus;
        public ushort[] continueCount;
    }

    internal class AbnormalCheckAck
    {
        public string cmd;
        public int stateCode;
        public List<AbnormalRecord> record;
    }
    internal class VersionAck
    {
        public string cmd;
        public int stateCode;
        public string FVer;
        public string LVer;
    }
    public enum MesClientState
    {
        STATE_INIT,
        STATE_WORING,
        STATE_POWER_OFF,// 启动错误
    }
    public enum MesClientEvent
    {
        EVT_NONE,
        EVT_STATE_INIT,
        EVT_LAUNCH_ERROR,// 启动错误
        EVT_LAUNCH_OK,
        EVT_STATE_NOTIFY,
        EVT_STATE_NOTIFY_RESP,
        EVT_STATE_CHECK,
        EVT_LAST_STATE_CHECK,// 最近状态
        EVT_ABNORMAL_CHECK,// 异常查询
        EVT_VERSION_CHECK,// 版本查询
        EVT_CONFIG_CHECK,
        EVT_EXIT_REQ,
        EVT_DESTORY,
    }

    public enum AckCode
    {
        none,
        paramError
    }

    public class MesClientService : StateMechine<MesClientState, MesClientEvent>
    {
        private TcpClientConn _conn;
        private static MesClientService _instance;
        private MesClientConfig _config;
        private byte[] _recvDataBuf;
        private const int MAX_BUF_SIZE = 512;
        private int _bufRecvSize = 0;
        private readonly Object _recvLock = new object();
        private static readonly Object _classLock = new object();
        private Timer _recvTimer;
        private TimerTask _timerTask;
        private MesClientEvent _retryEvent = MesClientEvent.EVT_NONE;
        private int _retryCount = 0;
        private int _retryTimerId = TimerTask.INVALID_TIMER_ID;// 任务重试
        private bool _launchFailed = false;
        private string _launchErrorMsg = "";
        private BSController _bsController;
        private TsConfig _workConfig;
        private TeamStateManager _teamStateManager;
        public Action ICloseMainWnd;
        public string _frameVersion;// Ui 版本
        public string _libVersion;// 库版本
        public static MesClientService GetInstance()
        {
            if (_instance == null)
            {
                lock (_classLock)
                {
                    if (_instance == null)
                    {
                        _instance = new MesClientService();
                    }
                }
            }
            return _instance;
        }
        private MesClientService() : base("MesClient")
        {
            _config = new MesClientConfig();
            _workConfig = new TsConfig();
            _conn = new TcpClientConn(OnRecvDataHandle, OnConnStateChange);
            _recvDataBuf = new byte[MAX_BUF_SIZE];
            _timerTask = TimerTask.GetTimerTaskInstance();
            _recvTimer = new Timer(RecvTimerCallback, null, Timeout.Infinite, Timeout.Infinite);
            RegistEventHandler();
        }
        public void RegistSystemVersion(string fwVer, string libVer)
        {
            _frameVersion = fwVer;
            _libVersion = libVer;
        }
        private void RecvTimerCallback(object state) // clear recv buf.
        {
            lock (_recvLock)
            {
                _bufRecvSize = 0;
            }
        }

        private bool OnRecvDataHandle(byte[] data)
        {
            int recvLen = data.Length;
            _recvTimer.Change(0, 500);
            lock (_recvLock)
            {
                if (_bufRecvSize + recvLen > MAX_BUF_SIZE)
                {
                    _bufRecvSize = 0;
                    recvLen = recvLen > MAX_BUF_SIZE ? MAX_BUF_SIZE : recvLen;
                }
                Array.Copy(data, 0, _recvDataBuf, _bufRecvSize, recvLen);
                _bufRecvSize += recvLen;
                if (OnRecvDataParse(_recvDataBuf, _bufRecvSize))
                {
                    _recvTimer.Change(Timeout.Infinite, 0);
                }
            }
            return true;
        }

        private void OnConnStateChange(bool connected)
        {

        }
        private bool OnRecvDataParse(byte[] data, int len)
        {
            bool ret = false;
            string recvMsg = UTF8Encoding.Default.GetString(data, 0, len);
            try
            {
                JObject obj = JObject.Parse(recvMsg);
                if (obj != null)
                {
                    string cmd = (string)obj["cmd"];
                    if (cmd != null)
                    {
                        int boxId = 0;
                        switch (cmd)
                        {
                            case "StateAck":
                                OnStateReportAck();
                                return true;
                            case "StateCheck":
                                OnStateCheck();
                                return true;
                            case "ConfigCheck":
                                OnConfigCheck();
                                return true;
                            case "ReqClose":
                                OnCloseReq();
                                return true;
                            case "BoxCheck":
                                boxId = (int)obj["boxId"];
                                OnBoxLastStateCheck(boxId);
                                return true;
                            case "AbnormalCheck":
                                boxId = (int)obj["boxId"];
                                OnAbnormalCheck(boxId);
                                return true;
                            case "VerCheck":
                                OnVersionCheck();
                                return true;
                        }
                    }
                }
            }
            catch
            {

            }
            return ret;
        }
        private void OnStateReportAck()
        {
            PostEventAsync(MesClientEvent.EVT_STATE_NOTIFY_RESP);
        }
        private void OnStateCheck()
        {
            PostEventAsync(MesClientEvent.EVT_STATE_CHECK);
        }
        private void OnConfigCheck()
        {
            PostEventAsync(MesClientEvent.EVT_CONFIG_CHECK);
        }

        private void OnAbnormalCheck(int boxId)
        {
            PostEventAsync(MesClientEvent.EVT_ABNORMAL_CHECK, boxId);
        }
        private void OnVersionCheck()
        {
            PostEventAsync(MesClientEvent.EVT_VERSION_CHECK);
        }
        private void OnBoxLastStateCheck(int boxId)
        {
            PostEventAsync(MesClientEvent.EVT_LAST_STATE_CHECK, boxId);
        }

        private void OnCloseReq()
        {
            PostEventAsync(MesClientEvent.EVT_EXIT_REQ);
        }

        public override void Run()
        {
            StartSync(MesClientState.STATE_INIT);
        }
        public void RegistEventHandler()
        {
            RegisterStateHandle(MesClientState.STATE_INIT, MesClientEvent.EVT_STATE_INIT, DoActionFirstInit);
            RegisterStateHandle(MesClientState.STATE_INIT, MesClientEvent.EVT_LAUNCH_ERROR, DoActionLaunchError);
            RegisterStateHandle(MesClientState.STATE_INIT, MesClientEvent.EVT_LAUNCH_OK, DoActionLaunchOk);
            RegisterStateHandle(MesClientState.STATE_INIT, MesClientEvent.EVT_STATE_NOTIFY_RESP, DoActionNotifyStateGetResp);
            RegisterStateHandle(MesClientState.STATE_INIT, MesClientEvent.EVT_EXIT_REQ, DoActionExitReq);
            RegisterStateHandle(MesClientState.STATE_INIT, MesClientEvent.EVT_DESTORY, DoActionExitRep);
            RegisterStateHandle(MesClientState.STATE_INIT, MesClientEvent.EVT_VERSION_CHECK, DoActionVersionCheck);

            RegisterStateHandle(MesClientState.STATE_POWER_OFF, MesClientEvent.EVT_STATE_INIT, DoActionEntryPoweroff);

            // RegisterStateHandle(MesClientState.STATE_WORING, MesClientEvent.EVT_LAUNCH_OK, DoActionLaunchOk);
            //RegisterStateHandle(MesClientState.STATE_WORING, MesClientEvent.EVT_STATE_NOTIFY_RESP, DoActionNotifyStateGetResp);
            RegisterStateHandle(MesClientState.STATE_WORING, MesClientEvent.EVT_STATE_CHECK, DoActionStateCheck);
            RegisterStateHandle(MesClientState.STATE_WORING, MesClientEvent.EVT_CONFIG_CHECK, DoActionConfigCheck);
            RegisterStateHandle(MesClientState.STATE_WORING, MesClientEvent.EVT_ABNORMAL_CHECK, DoActionBoxAbnormalCheck);
            RegisterStateHandle(MesClientState.STATE_WORING, MesClientEvent.EVT_VERSION_CHECK, DoActionVersionCheck);
            RegisterStateHandle(MesClientState.STATE_WORING, MesClientEvent.EVT_LAST_STATE_CHECK, DoActionBoxCheck);
            RegisterStateHandle(MesClientState.STATE_WORING, MesClientEvent.EVT_EXIT_REQ, DoActionExitReq);
            RegisterStateHandle(MesClientState.STATE_WORING, MesClientEvent.EVT_DESTORY, DoActionExitRep);

        }
        protected override void NotifyStateChange(MesClientState state)
        {
            PostEventAsync(MesClientEvent.EVT_STATE_INIT);
        }
        #region event handler
        private MesClientState DoActionFirstInit(Object param)
        {
            _conn.OpenConn(_config.IPAddr, _config.Port);
            return MesClientState.STATE_INIT;
        }
        private void SendData(object message)
        {
            string sendStr = JsonConvert.SerializeObject(message);
            byte[] sendData = UTF8Encoding.Default.GetBytes(sendStr);
            for (int i = 0; i < 3; i++)
            {
                if (_conn.SendData(sendData, sendData.Length))
                {
                    break;
                }
                Task.Delay(1000).Wait();
            }
        }
        private MesClientState DoActionLaunchOk(Object param)
        {
            StateReport report = new StateReport();
            report.cmd = "StateChange";
            report.detail = "";
            report.stateCode = StateReport.STATE_CODE_OK;
           
            SendData(report);
            StartRetryTimer(2000, MesClientEvent.EVT_LAUNCH_OK);
            return MesClientState.STATE_INIT;
        }
        private MesClientState DoActionNotifyStateGetResp(Object param)
        {
            StopRetryTimer();
            if (_launchFailed)
            {
                return MesClientState.STATE_POWER_OFF;
            }
            _teamStateManager = TeamStateManager.GetInstance();
            return MesClientState.STATE_WORING;
        }
        private MesClientState DoActionStateCheck(Object param)
        {
            if(_bsController != null)
            {
                WorkStateAck ack = new WorkStateAck();
                ack.cmd = "StateAck";
                if(_bsController.IsWorking())
                {
                    ack.stateCode = 1;
                }else
                {
                    ack.stateCode = 0;
                }
                SendData(ack);
            }
            return MesClientState.STATE_WORING;
        }
        private MesClientState DoActionConfigCheck(Object param)
        {
            ConfigResponse response = new ConfigResponse();
            response.config = _workConfig;
            response.cmd = "ConfigAck";
            SendData(response);
            return MesClientState.STATE_WORING;
        }

        private MesClientState DoActionBoxCheck(Object param)
        {
            int boxId = 0;
            BoxCheckAck ack = new BoxCheckAck();
            ack.cmd = "BoxCheckAck";
            if (param != null && int.TryParse(param.ToString(),out boxId) && boxId > 0 && boxId<= SysConfig.DEV_NUM)
            {
                ack.continueCount = Array.Empty<ushort>();
                ack.memberStatus = Array.Empty<ushort>();
                _teamStateManager.LoadTeamMemberLastStateCode(boxId - 1, ref ack.memberStatus, ref ack.continueCount);
                ack.stateCode = (int)AckCode.none;
            }
            else
            {
                ack.stateCode = (int)AckCode.paramError;
            }
            SendData(ack);
            return MesClientState.STATE_WORING;
        }

        private MesClientState DoActionBoxAbnormalCheck(Object param)
        {
            int boxId = 0;
            AbnormalCheckAck ack = new AbnormalCheckAck();
            ack.cmd = "AbnormalAck";

            if (param != null && int.TryParse(param.ToString(), out boxId) && boxId > 0 && boxId <= SysConfig.DEV_NUM)
            {
                List<AbnormalRecord> record = new List<AbnormalRecord>();
                _teamStateManager.LoadTeamMemberEvtAbnormalRecord(boxId - 1, ref record);
                ack.stateCode = (int)AckCode.none;
                ack.record = record;
            }
            else
            {
                ack.stateCode = (int)AckCode.paramError;
            }
            SendData(ack);
            return MesClientState.STATE_WORING;
        }

        private MesClientState DoActionVersionCheck(Object param)
        {
            VersionAck ack = new VersionAck();
            ack.cmd = "VerAck";
            ack.FVer = _frameVersion;
            ack.LVer = _libVersion;
            ack.stateCode = (int)AckCode.none;
            SendData(ack);
            return CurState;// 不改变状态
        }

        

        private MesClientState DoActionExitReq(Object param)
        {
            ExitAck ack = new ExitAck();
            ack.cmd = "CloseResp";
            ack.stateCode = 0;
            if (_bsController != null)
            {
              if(_bsController.IsWorking())
                {
                    ack.stateCode = 1;
                    ack.detail = "test is running.";
                    SendData(ack);
                }
                else
                {
                    ICloseMainWnd?.Invoke();
                }
            }
            else
            {
                SendData(ack);
                ICloseMainWnd?.Invoke();
                return MesClientState.STATE_POWER_OFF;
            }
            return MesClientState.STATE_WORING;
        }

        private MesClientState DoActionExitRep(Object param)
        {
            ExitAck ack = new ExitAck();
            ack.cmd = "CloseResp";
            ack.stateCode = 0;
            SendData(ack);
            return MesClientState.STATE_POWER_OFF;
        }


        private MesClientState DoActionLaunchError(Object param)
        {
            string errorMsg = _launchErrorMsg;
            StateReport report = new StateReport();
            report.cmd = "StateChange";
            report.detail = errorMsg;
            report.stateCode = StateReport.STATE_CODE_LAUNCH;
            string sendStr = JsonConvert.SerializeObject(report);
            byte[] sendData = UTF32Encoding.Default.GetBytes(sendStr);
            _conn.SendData(sendData, sendData.Length);
            if (_retryCount < 3)
            {
                StartRetryTimer(2000, MesClientEvent.EVT_LAUNCH_ERROR);
                return MesClientState.STATE_INIT;
            }
            return MesClientState.STATE_POWER_OFF;
        }
        private MesClientState DoActionEntryPoweroff(Object param)
        {
           // Environment.Exit(0);
            return MesClientState.STATE_POWER_OFF;
        }
        #endregion

        #region timeout retry
        private void StartRetryTimer(int msecond, MesClientEvent eventId)
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
            Hlog.I(Mod, "start retry timer team");
        }
        private void StopRetryTimer()
        {
            if (_retryTimerId != TimerTask.INVALID_TIMER_ID)
            {
                _timerTask.StopTimer(ref _retryTimerId);
                _retryCount = 0;
            }
        }
        private void RetryActionTimeout(int timerId)
        {
            Hlog.I(Mod, "retry action timeout team");
            if (timerId == _retryTimerId)
            {
                _retryTimerId = TimerTask.INVALID_TIMER_ID;
                PostEventAsync(_retryEvent);
            }
        }
        #endregion

        public void OnLaunchError(string message)
        {
            _launchErrorMsg = message;
            _launchFailed = true;
            PostEventAsync(MesClientEvent.EVT_LAUNCH_ERROR);
        }

        public void OnLaunchOK(BSController controller)
        {
            _bsController = controller;
            PostEventAsync(MesClientEvent.EVT_LAUNCH_OK);
        }

        public void LoadConfigInfor(SlaveModeConfig config, string configName)
        {
            _workConfig.MaterialNo = config.MaterialNo;
            _workConfig.OrderNo = config.OrderNo;
            _workConfig.ProcessesId = config.ProcessesId;
            _workConfig.WorkOrderNo = config.WorkOrderNo;
            _workConfig.TSPath = config.TSPath;
            _workConfig.TempState = config.TempState;
            _workConfig.ProcessesId = config.ProcessesId;
            _workConfig.TSName = configName;
        }
        public void Destory()
        {
            Stop(MesClientEvent.EVT_DESTORY);
        }
    }


}
