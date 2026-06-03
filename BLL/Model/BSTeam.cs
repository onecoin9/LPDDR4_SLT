using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Net;
using Hsg.Common;
using Hsg.BLL.Net;
using Hsg.BLL.config;
using static Hsg.BLL.DutMaster;

namespace Hsg.BLL.Model
{

    public partial class BSTeam
    {
        //  private UInt16 _dutEnableFlags;
        private byte[] _dutsErrorCode;
        private byte[] _dutsBinCode;
        private ushort[] _stateCodes;
        private string[] _lastEnvTemp;
        /// <summary>
        /// 标记是否有测试任务 gropu
        /// </summary>
        private bool[] _groupExcuteFlags;
        /// <summary>
        /// 二维数组，表示对应通讯板上它的dut 是否有任务
        /// </summary>
        private bool[,] _dutsMangerExecuteFlag;
        /// <summary>
        /// 代表所有测试板是否需要执行任务,只在最初请求的时候同步状态
        /// </summary>
        private bool[] _dutExecuteFlag;
        private const string MOD_ID = "BSTeam";
        private string _taskSerialNo;// 任务序号
        private UInt32[] _stageFailCount;// 每个段失败的统计
        //用来加严复测多次成功才上报
        private int _excuteCount
        {
            get { return _viewModel.ExcuteCount; }
            set { _viewModel.ExcuteCount = value; }
        }
        private UInt32[] _retryPassCount;
        private UInt32[] _retryFailCount;
        private bool[] _retryWithFail;// 是否有失败的记录（排除超时和环境异常)
                                      // private bool[,] _retryDutsManagerFlag;

      //  private DateTime _testStartTime;
        // 屏蔽任务执行请求，避免执行过程有二次请求
        private bool _taskExecLock;
        public TestStage GetMemberState(int groupId)
        {
            return _dutsManagerList[groupId].TestStage;
        }

        // private TestStage _stage { set { _viewModel.Stage = value; } }
        public TestStage Stage
        {
            get { return _viewModel.Stage; }
            set
            {
                if (_viewModel.Stage != value)
                {
                    _viewModel.Stage = value;
                    _onStageChange?.Invoke(_instanceId, _viewModel.Stage);
                }
            }
        }

        private bool _workModeOpen
        {
            get { return _viewModel.WorkModeOpen; }
            set { _viewModel.WorkModeOpen = value; }
        }
        /// <summary>
        /// 启动状态业务
        /// </summary>
        public override void Run()
        {
            Start(BSTState.ST_INIT);
        }

        public void EntryWorkMode()
        {
            _workModeOpen = true;
        }

        public void ExitWorkMode()
        {
            PostEventAsync(BSTEvent.EVT_CANCEL_TASK);
            _workModeOpen = false;
        }

        public void CancelWorkMode()
        {
            AppendLogToUi("请求取消当前任务", LOG_TYPE.WARNNING);
            PostEventAsync(BSTEvent.EVT_CANCEL_TASK);
        }


        public void Destory()
        {
            UnbindUi();
            Stop(BSTEvent.EVT_DESTORY);
        }

        public bool ExcuteTestTask(bool[] flags) // 可能需要多线程保护
        {
            if (CurState != BSTState.ST_READY && CurState != BSTState.ST_WORKE_END || _taskExecLock)
            {
                if (_taskExecLock)
                {
                    AppendLogToUi("任务执行中，不支持重复任务", LOG_TYPE.ERROR);
                    return false;
                }
                AppendLogToUi("状态非就绪, 不存在可以执行命令的条件", LOG_TYPE.ERROR);
                return false;
            }
            _taskExecLock = true;

            // 清除测试状态
            Array.Clear(_groupExcuteFlags, 0, BSTeamConfig.GROUP_COUNT);
            Array.Clear(_dutsErrorCode, 0, _dutsErrorCode.Length);
            Array.Clear(_stateCodes, 0, _stateCodes.Length);
            Array.Clear(_dutsExcuteStageCount, 0, _dutsExcuteStageCount.Length);
            if (flags.GetLength(0) <= BSTeamConfig.DUTS_COUNT)
            {
                for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++)
                {
                    int groupId = 0;
                    int id = 0;
                    DutsLogicalMap.ConventUIdToGroupDutId(i, ref groupId, ref id);

                    _dutsMangerExecuteFlag[groupId, id] = flags[i];
                    if (flags[i])
                    {
                        _groupExcuteFlags[groupId] = true;
                        if (_dutsManagerList[groupId].TestStage != TestStage.ST_READY
                            && _dutsManagerList[groupId].TestStage <= TestStage.ST_TESTING)
                        {
                            AppendLogToUi($"Group[{groupId}] 状态{_dutsManagerList[groupId].TestStage} 不支持新的任务", LOG_TYPE.ERROR);
                            _taskExecLock = false;
                            return false;
                        }
                    }
                    Array.Clear(_dutExecuteFlag, 0, _dutExecuteFlag.Length);
                    Array.Copy(flags, _dutExecuteFlag, flags.Length);
                    //_execDutsFlag[i] = flags[i];
                }
                AppendLogToUi("收到任务请求", LOG_TYPE.WARNNING);
                // 清除所有dut的原来状态
                for (int i = 0; i < BSTeamConfig.GROUP_COUNT; i++)
                {
                    _dutsManagerList[i].ResetAllDutsState();
                }
                PostEventAsync(BSTEvent.EVT_EXCUTE_TEST, null);
                return true;
            }
            else
            {
                AppendLogToUi("数据不合法,请求测试失败", LOG_TYPE.ERROR);
            }
            _taskExecLock = false;
            return false;
        }

        //public byte[] GetDutsErrorCode()
        //{
        //    return _dutsErrorCode;
        //}


        public byte[] GetDutsBinCode()
        {
            return _dutsBinCode;
        }

        public TestStage GetDutStage(int dutId)
        {
            return _viewModel.DutStates[dutId];
        }
        public void TempCtrOpen()
        {
            if (!_bsTeamConfig.OpenTempMgr)
            {
                return;
            }
            Hlog.I("start temp:" + _stateName);
            _tempTeamCtr.StartWork();
        }
        public void TriggerDutFail(int dutId)
        {
            //if (dutId >= 0 && dutId < _dutList.Count)
            //{
            //    _dutList[dutId].TriggerFaileType();
            //}
        }
        public void RefreshEnverionment()
        {
            if (CurState != BSTState.ST_WORKING)
            {
                if(_execDelayForTemp)
                {
                    AppendLogToUi("当前任务正在等待执行，不支持重置测试环境", LOG_TYPE.ERROR);
                }
                else
                {
                    PostEventAsync(BSTEvent.EVT_ENV_RETRY);
                    AppendLogToUi("重启测试环境", LOG_TYPE.WARNNING);
                }
                return;
            }
        }

        public void RetryAbnormalTestGroup()
        {
            if (_viewModel.AlarmFlag)
            {
                PostEventAsync(BSTEvent.EVT_ABNORMAL_RETRY);
            }
        }

        public void PauseAlarmCountdown()
        {
            if (_abnormalWait)
            {
                PostEventAsync(BSTEvent.EVT_PAUSE_ALARM_COUNTDOWN);
            }
        }

        public void ResumeAlarmCountdown()
        {
            if (_abnormalWait)
            {
                PostEventAsync(BSTEvent.EVT_RESUME_ALARM_COUNTDOWN);
            }
        }
        public UInt32 GetStageFailCount(int stageIndex)
        {
            if (stageIndex >= 0 && stageIndex < _stageFailCount.Length)
            {
                return _stageFailCount[stageIndex];
            }
            return 0;//invalid stageIndex
        }
    }
}
