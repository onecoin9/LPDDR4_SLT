using Hsg.BLL.Service;
using Hsg.Common;
using Newtonsoft.Json.Bson;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.Model
{
    public partial class DutsManager
    {
        private List<DutMaster> _dutList;
        private bool[] _dutExcuteFlags;
        private byte[] _dutsErrorCode;
        private ushort[] _dutsStateCode;
        private string[] _dutsLastEvtInfo;//最近的测试环境温度信息
        private UInt16 _dutEnableFlags;
        private UInt32 _startTimestamp;
        private bool _communicateBoardRebootCheck = false;
        private TestBoardConfig _testBoardCfg; // 当前测试选用的配方
        private DMUIState uiState;
        private string _stageInfo;// 测试阶段信息，用来记录在测试信息中
        private string _repeatInfo;// 重复次数信息
        private string _taskSerialNo;// 测试任务编号
        private DateTime[] _dutsFinishTime;// dut任务结束时间
        public AlarmType AlarmState { get; internal set; }
        private TestStage _stage = TestStage.ST_NOT_START;
        public TestStage TestStage
        {
            get { return _stage; }
            private set
            {
                if (_stage != value)
                {
                    _stage = value;
                    if (_onStageChange != null)
                    {
                        _onStageChange(_instanceId, _groupId, _stage);
                    }
                }
            }
        }
        public override void Run()
        {
            base.Start(DMState.ST_INIT);
        }
        public bool GenerateIOGroupControl(out ushort[] data)
        {
            data = null;
            if (_dutManagerCfg.IOCtrAId > 0)
            {
                return CBCProtocol.GenerateGroupSetPackage(_dutManagerCfg.IOCtrAId, _dutManagerCfg.IOCtrAStart, _dutManagerCfg.IOCtrASpan, out data);
            }
            return false;
        }
        public bool ExcuteTestTask(bool[] flags, TestBoardConfig testBoardCfg, int delayTime = 0, string repeatInfo = "None", string stageInfo = "None", string taskSerialNo = "--") // 可能需要多线程保护
        {
            if (CurState != DMState.ST_READY && CurState != DMState.ST_WORKE_END)
            {
                // 状态为IDLE或ONLINE表示正在恢复中，保存参数并尝试触发恢复，安排重试
                if (CurState == DMState.ST_IDLE || CurState == DMState.ST_ONLINE)
                {
                    AppendLogToUiSimple("板卡未就绪, 尝试重新连接后重试测试", LOG_TYPE.WARNNING);
                    Array.Copy(flags, _dutExcuteFlags, flags.Length > _dutExcuteFlags.Length ? _dutExcuteFlags.Length : flags.Length);
                    _stageInfo = stageInfo;
                    _repeatInfo = repeatInfo;
                    _taskSerialNo = taskSerialNo;
                    _communicateBoardRebootCheck = false;
                    _testBoardCfg = testBoardCfg;
                    PostEventAsync(DMEvent.EVT_RSET_STATE);
                    StartRetryTimer(5000, DMEvent.EVT_EXCUTE_TEST);
                    return true;
                }
                AppendLogToUiSimple("状态非就绪, 状态:" + CurState.ToString(), LOG_TYPE.ERROR);
                return false;
            }

            if (flags.GetLength(0) <= _dutList.Count)
            {
                Array.Copy(flags, _dutExcuteFlags, flags.Length > _dutExcuteFlags.Length ? _dutExcuteFlags.Length : flags.Length);
                _stageInfo = stageInfo;
                _repeatInfo = repeatInfo;
                _taskSerialNo = taskSerialNo;
                _communicateBoardRebootCheck = false;
                _testBoardCfg = testBoardCfg;
                PostEventAsync(DMEvent.EVT_EXCUTE_TEST, delayTime);
                return true;
            }
            else
            {
                AppendLogToUiSimple("数据不合法,请求测试失败", LOG_TYPE.ERROR);
            }
            return true;
        }

        public void CancelWorkMode()
        {
            PostEventAsync(DMEvent.EVT_CANCEL_TASK);
        }
        public void ExcuteDutsTempBad(int dutId, float value, bool mainBoardError = false)
        {
            _dutList[dutId].SetTempError(value, mainBoardError);
        }
        public void ExcuteTimeout()
        {
            PostEventAsync(DMEvent.EVT_TIMEOUT);
        }

        public byte[] GetErrorCode()
        {
            return _dutsErrorCode;
        }
        public ushort[] GetStateCode()
        {
            return _dutsStateCode;
        }
        public string[] GetLastTempValue()
        {
            return _dutsLastEvtInfo;
        }

        public DateTime GetDutFinishDateTime(int dutIndex)
        {
            return _dutsFinishTime[dutIndex];
        }
        public void Destory()
        {
            UnbindUi();
            Stop(DMEvent.EVT_DESTORY);
            _cbcControl.Destory();
        }
        /// <summary>
        /// 保存记录
        /// </summary>
        /// <param name="saveAll">是否保存全部，如果为fals ,则只保存失败</param>
        public void OnSaveDutsTestResult(bool saveAll = true)
        {
            for (int i = 0; i < _dutExcuteFlags.Length; i++)
            {
                if (_dutExcuteFlags[i])
                {
                    if (_dutList[i].GetErrorCode() == DutMaster.ERR_CODE_OK)
                    {
                        if (saveAll)
                        {
                            _dutList[i].SaveTestResult();
                        }
                    }
                    else
                    {
                        _dutList[i].SaveTestResult();
                    }
                }
            }
        }
        /// <summary>
        /// 保存加严复测模式的最终结果
        /// </summary>
        /// <param name="saveFlag"></param>
        /// <param name="startTime"></param>
        /// <param name="passCount"></param>
        /// <param name="failCount"></param>
        /// <param name="errCodes"></param>
        //public void SaveFixedTaskRecord(UInt32 recordInstance, bool[] saveFlag, DateTime startTime, /*UInt32[] passCount, UInt32[] failCount,*/ byte[] errCodes)
        //{
        //    for (int i = 0; i < saveFlag.Length && i < _dutList.Count; i++)
        //    {
        //        if (!saveFlag[i])
        //        {
        //            continue;
        //        }
        //        _dutList[i].SaveRetryTaskFixedRecord(recordInstance, BSController.TestRecord.GetRecordObject(), startTime, /*passCount[i], failCount[i],*/ errCodes[i]);
        //    }
        //}
        public void ResetAllDutsState()
        {
            if (CurState != DMState.ST_WORKING)
            {
                uiState.ResetDutsState();
                for (int i = 0; i < _dutList.Count; i++)
                {
                    _dutList[i].ResetWorkStatus(); // 不参与测试的让其恢复到默认状态
                }
            }
            else
            {
                Hlog.E(Mod, "reset duts state invalid");
            }
        }
        public void ResetStatus()
        {
            PostEventAsync(DMEvent.EVT_RSET_STATE);
        }


        public void CommunicateBoardRebootCheck()
        {
            _communicateBoardRebootCheck = true;
        }
        public void SyncLastStatus(TestStage stage, int dutId) // 暂时没有多线程保护
        {
            if (CurState == DMState.ST_WORKE_END && dutId < _dutList.Count)
            {
                uiState.DutsState[dutId] = stage;
            }
        }

    }
}
