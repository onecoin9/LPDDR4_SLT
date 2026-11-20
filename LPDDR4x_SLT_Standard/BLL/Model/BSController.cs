using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Threading;
using System.Net;
using Hsg.Common;
using Hsg.BLL.Net;
using Hsg.BLL.config;
using Hsg.BLL.Policy;
using Newtonsoft.Json;
using Hsg.BLL.ViewModel;
using Hsg.BLL.Service;

namespace Hsg.BLL.Model
{
    public partial class BSController
    {



        //public static CSVRecord TestInfoCSV = new CSVRecord("Test_info." + DateTime.Now.ToString("yyyy-MM-dd"), SysConfig.GetInstance().CSVTitle.Value);
        private IBSViewModel _viewModel;
        //private readonly static HsgLogger _logger = new HsgLogger();
        private static readonly object _stateLock = new object();
        private const string MOD_ID = "BC";
        private BSConfig _bsConfig;
        public static BSRecord TestRecord;
        public static BSRecord DetailRecord;
        private BSRecord _overviewRecord;
        private const string TEST_RECORD_NAME = "Record"; // 一个测试结果
        private const string DETAIL_RECORD_NAME = "Detail";// 记录一个测试中，包含的测试详情，如每个阶段，复测每次的异常
        private const string OVERVIEW_RECORD_NAME = "Overview";
        private UInt32[] _binRecord;// 每个bin 的计数
        private int _alarmSerial = 0;

        // private NamePipeServer _namePipeSvr;


        /// <summary>
        /// 开始业务逻辑,用于UI线程启动后调用，避免堵塞UI线程
        /// </summary>
        public override void Run()
        {
            // 启动自身
            base.StartSync(BSCStatus.ST_INIT);
        }
        /// <summary>
        /// 停止业务逻辑
        /// </summary>
        public bool StopService()
        {
            if (_viewModel.TestingTeamNum > 0)
            {
                AppendLogToUi("当前有正在执行的测试，请先取消任务", LOG_TYPE.WARNNING);
                return false;
            }
            base.PostEventAsync(BSCEvent.EVT_STOP_SERVICE);
            AppendLogToUi("关闭测试服务", LOG_TYPE.WARNNING);
            return true;
        }
        /// <summary>
        /// 进入工作状态
        /// </summary>
        public void StartService()
        {
            base.PostEventAsync(BSCEvent.EVT_START_SERVICE);
        }
        /// <summary>
        /// 退出程序关闭业务
        /// </summary>
        public void DestoryService()
        {
            UnbindUi();
            _tcpServer.Stop();
            _tbCommunicateService.StopService();

            Stop(BSCEvent.EVT_DESTORY);
            if (SysConfig.WorkMode == WorkMode.Slave)
            {
                MesClientService msClient = MesClientService.GetInstance();
                msClient.Destory();
            }
        }
        /// <summary>
        /// 请求执行测试任务
        /// </summary>
        /// <param name="teamIndex"></param>
        /// <param name=""></param>
        private void OnConfigChange(UInt32 param)
        {
            if ((param & BSConfig.ATTR_EMI) != 0)
            {
                LoadPolicyFile();
            }
        }
              public bool IsWorking()
        {
            return (_viewModel.TestingTeamNum > 0) || !CheckResultSendFinish();
        }


        //public void SetDebugMode(bool _debugOn)
        //{
        //    SystemStatus.DebugMode = _debugOn;
        //}
        public bool IsDebugMode() { return SystemStatus.DebugMode; }

        public bool IsStartService() { return _viewModel.ServiceStart; }
        /// <summary>
        /// 用于调试
        /// </summary>
        /// <param name="teamId"></param>
        public void OnImitateTest(int teamId)
        {
            if(PolicyManager.Instance.Policy == null)
            {
                AppendLogToUi("当前无可执行的测试方案", LOG_TYPE.ERROR);
                return;
            }
            if (teamId < _teamList.Count && teamId >= 0)
            {
                bool[] teamFlag = new bool[BSTeamConfig.DUTS_COUNT];

                for (int i = 0; i < BSTeamConfig.GROUP_COUNT; i++)
                {
                    if (_teamList[teamId].GetMemberState(i) >= TestStage.ST_READY)
                    {
                        for (int j = 0; j < BSTeamConfig.ITEM_DUT_NUM; j++)
                        {
                            int uid = DutsLogicalMap.ConventIdToUI(j, i);
                            teamFlag[uid] = true;
                        }
                    }
                }
                _teamList[teamId].ExcuteTestTask(teamFlag);
            }
            if(!_recordStart)
            {
                _recordStart = true;
                _startWorkTime = DateTime.Now;
            }
        }

        public void OnCancelTest(int teamId)
        {
            if (teamId < _teamList.Count && teamId >= 0)
            {
                _teamList[teamId].CancelWorkMode();
            }
        }
        public void OnRetryAbnormalTest(int teamId)
        {
            if (teamId < _teamList.Count && teamId >= 0)
            {
                _teamList[teamId].RetryAbnormalTestGroup();
            }
        }

        public void OnPauseAlarmCountdown(int teamId)
        {
            if (teamId < _teamList.Count && teamId >= 0)
            {
                _teamList[teamId].PauseAlarmCountdown();
            }
        }

        public void OnResumeAlarmCountdown(int teamId)
        {
            if (teamId < _teamList.Count && teamId >= 0)
            {
                _teamList[teamId].ResumeAlarmCountdown();
            }
        }

        public bool ReceiveConnIsReady()
        {
            return _dutsConnReady;
        }

        public void NotifyBoardOnline(int teamId)
        {
            if (teamId >= 0 && teamId < _teamList.Count)
            {
                _teamList[teamId].NotifyBoardOnline();
            }
        }

        public void NotifyBoardOnline(int teamId, int groupId, bool fromLogChannel)
        {
            if (teamId >= 0 && teamId < _teamList.Count)
            {
                _teamList[teamId].NotifyBoardOnline(groupId, fromLogChannel);
            }
        }

        public bool TempControlIsOpen()
        {
            return _bsConfig.OpenTempMgr;
        }
        public void RefreshEnverionment(int teamId)
        {
            if (teamId >= 0 && teamId < _teamList.Count)
            {
                _teamList[teamId].RefreshEnverionment();
            }
        }
        private void OnLogPipeMsgHandle(string msg)
        {
            try
            {
                dynamic jsonObject = JsonConvert.DeserializeObject(msg);
                int boardId = jsonObject.board;
                int dut = jsonObject.dut;
                if (boardId >= 1 && boardId <= _teamList.Count)
                {
                    _teamList[boardId - 1].TriggerDutFail(dut);
                }
            }
            catch
            {
            }
        }

        private void OnLogPipeStateChange(bool isReady)
        {
            if (isReady)
            {
                AppendLogToUi("日志检测的管道已连接", LOG_TYPE.DONE);
            }
            else
            {
                AppendLogToUi("日志检测的管道连接失败", LOG_TYPE.ERROR);
            }
        }

        public bool CheckWorkEnvironment(ref string errorMsg)
        {
            bool ret = true;
            if (!_initDone)
            {
                errorMsg += "正在初始化，请等待。\r\n";
                return false;
            }
            if (PolicyManager.Instance == null)
            {
                ret = false;
                errorMsg += "没有有效的测试脚本配置，或者没有有效工单\r\n";
            }
            if (!_dutsConnReady)
            {
                ret = false;
                errorMsg += "通讯UDP 端口 未就绪，可能存在端口冲突\r\n";
            }

            if(!TestRecord.GetRecordObject().CheckFileIsReady())
            {
                ret = false;
                errorMsg += $"{TEST_RECORD_NAME} 记录文件被占用，请关闭文件重启程序\r\n";
            }
            if (!DetailRecord.GetRecordObject().CheckFileIsReady())
            {
                errorMsg += $"{DETAIL_RECORD_NAME} 记录文件被占用，请关闭文件重启程序\r\n";
                ret = false;
            }
            if (!_overviewRecord.GetRecordObject().CheckFileIsReady())
            {
                _overviewRecord = new BSRecord(OVERVIEW_RECORD_NAME, _bsConfig.OverviewTitle, true);
                if(!_overviewRecord.GetRecordObject().CheckFileIsReady())
                {
                    errorMsg += $"{OVERVIEW_RECORD_NAME} 记录文件被占用，请关闭文件重启服务\r\n";
                    ret = false;
                }
            }
            return ret;
        }
        /// <summary>
        /// 测试结果是否全部同步。
        /// </summary>
        /// <returns></returns>
        private bool CheckResultSendFinish()
        {
            if (IsDebugMode())
            {
                return true;
            }
            foreach (bool v in _teamTestFinshFlags)
            {
                if (v)
                {
                    return false;
                }
            }
            return true;
        }
        /// <summary>
        /// 检查所有温控板连接状态，汇总打印到上位机
        /// </summary>
        public void CheckAllTempConnections()
        {
            List<string> connected = new List<string>();
            for (int i = 0; i < _teamList.Count; i++)
            {
                string status = _teamList[i].GetTempConnectivity();
                if (status.StartsWith("已连接"))
                    connected.Add($"Team{i + 1}");
            }
            if (connected.Count > 0)
                AppendLogToUi($"温控板已连接: {string.Join(", ", connected)}", LOG_TYPE.DONE);
            else
                AppendLogToUi("没有温控板能连接上", LOG_TYPE.ERROR);
            Hlog.I(Mod, $"温控板连接汇总: 已连={connected.Count}");
        }

        private void AddAlarmMsgToReport(int teamIndex, string alarmMsg)
        {
            if (!_viewModel.ServiceStart)
            {
                return;
            }
            lock (_opLock)
            {
                string value = "";
                if (!_alarmList.TryGetValue(teamIndex, out value))
                {
                    _alarmList.Add((int)teamIndex, alarmMsg);
                    PostEventAsync(BSCEvent.EVT_REPORT_MSG);
                }
            }
        }
        private bool SendAlarmToServer(int teamNo, string alarmMsg)
        {
            _alarmSerial = teamNo;
            byte[] sendData = HCProtocol.EncodeAlarmJson(alarmMsg);
            if (SendToHandlerByClient(sendData))
            {
                return true;
            }
            return false;
        }

        /// <summary>
        /// 短连接主动上报：建立连接 → 发送 → 等待 ACK → 断开
        /// </summary>
        private bool SendToHandlerByClient(byte[] sendData)
        {
            if (sendData == null || sendData.Length <= 0)
                return false;
            if (string.IsNullOrWhiteSpace(_handlerIp))
            {
                Hlog.E(Mod, "send to handler failed: handler ip unknown");
                return false;
            }
            LogHandlerJson("上报", sendData);

            byte[] response = TcpShortClient.Send(_handlerIp, _handlerPort, sendData);
            if (response != null)
            {
                LogHandlerJson("ACK", response);
                ProcessJsonResponse(response, response.Length);
                return true;
            }
            Hlog.E(Mod, "send to handler on short conn failed");
            return false;
        }

        private void RemoveAlarmMsgForReprot(int teamIndex)
        {
            lock (_opLock)
            {
                _alarmList.Remove(teamIndex);
            }
        }
    }
}
