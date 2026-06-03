using Hsg.BLL.config;
using Hsg.BLL.ViewModel;
using Hsg.Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.Model
{
    public partial class DutsManager
    {
        private IUIAppendLog _iUiAppendLog;

        public void BindUIUpdate(IUIAppendLog appendLog)
        {
            //if (!_enable)
            //{
            //    return;
            //}
            _iUiAppendLog += appendLog;
            if (SystemStatus.DebugMode == true)
            {
                for (int i = 0; i < _dutList.Count; i++)
                {
                    _dutList[i].BindUIUpdate(AppendLogToUiSimple);
                }
            }
        }
        private void AppendLogToUi(string log, LOG_TYPE type)
        {
            if (_iUiAppendLog != null)
            {
                _iUiAppendLog(string.Format(@"[板卡{0}] {1}", _groupId + 1, log), type);
            }
        }

        private void UnbindUi()
        {
            _iUiAppendLog = null;
            //for (int i = 0; i < _dutList.Count; i++)
            //{
            //    _dutList[i].UnbindUi();
            //}
        }
        private void AppendLogToUiSimple(string log, LOG_TYPE type)
        {
            if (_iUiAppendLog != null)
            {
                _iUiAppendLog(string.Format(@"[板卡{0}] {1}", _groupId + 1, log), type);
            }
        }
        private void AppendLogToDetil(string log, LOG_TYPE type)
        {
            uiState.AddStageDetail(log);
        }
    }

    internal class DMUIState
    {
        private int _groupId;
        public ObservableArray<TestStage> DutsState;
        private readonly Object _lockObj = new Object();
        private ITeamViewModel _teamViewModel;
        internal DMUIState(ITeamViewModel teamViewModel, int groupId)
        {
            _teamViewModel = teamViewModel;
            _groupId = groupId;
            DutsState = new ObservableArray<TestStage>(new TestStage[SysConfig.PORT_NUM]);
            _DutFinishRecord = new Tuple<string, string, ushort>[SysConfig.PORT_NUM];
            DutsState.OnArrayChange += OnDutsStateChange;
        }

        internal void UpdateStageDetail(IUpdateTeamDetail update)
        {

        }

        internal Tuple<string, string, ushort>[] _DutFinishRecord;


        /// <summary>
        /// 设备是否在线，主要检查IP是不是可以Ping通
        /// </summary>
        internal bool DevOnline
        {
            get
            {
                return _teamViewModel.GroupReady[_groupId];
            }
            set
            {
                _teamViewModel.GroupReady[_groupId] = value;
            }
        }



        private void OnDutsStateChange(int dutId, object param)
        {
            int uId = DutsLogicalMap.ConventIdToUI(dutId, _groupId);
            _teamViewModel.DutStates[uId] = DutsState[dutId];
            // Console.WriteLine("OnDutsStateChange:" + uId + DutsState[dutId]);
        }
        ///// <summary>
        ///// 检查是否已经全部超时
        ///// </summary>
        ///// <returns></returns>
        //public bool CheckDutsIsAllTimeout()
        //{
        //    bool ret = true;
        //    lock (_lockObj)
        //    {
        //        for (int i = 0; i < _DutsState.Count; i++)
        //        {
        //            if (_DutsState[i] == TestStage.ST_TEST_FAIL || _DutsState[i] == TestStage.ST_TEST_SUCCESS)
        //            {
        //                ret = false;
        //                break;
        //            }
        //        }
        //    }
        //    return ret;
        //}

        // 暂时频闭详情，提示系统效率。后期更具吸引可以开放
        internal void AddStageDetail(string detail)
        {
#if SUPPORT_GROUP_DETAIL
            if (_teamViewModel.GroupDetail[_groupId].Length > 0)
            {
                _teamViewModel.GroupDetail[_groupId] += "\r\n";
            }
            _teamViewModel.GroupDetail[_groupId] += "[" + DateTime.Now.ToString("HH:mm:ss") + "]";
            _teamViewModel.GroupDetail[_groupId] += detail;
#endif
        }
        internal void ResetDutsState()
        {
            for (int i = 0; i < DutsState.Length; i++)
            {
                DutsState[i] = TestStage.ST_READY;
                AddStageDetail("[" + (i + 1) + "]无任务");
            }
#if SUPPORT_GROUP_DETAIL
            _teamViewModel.GroupDetail[_groupId] = "";
#endif
        }
        internal void ResetDutState(int dutId)
        {
            if (dutId < DutsState.Length && dutId >= 0)
            {
                DutsState[dutId] = TestStage.ST_READY;
                AddStageDetail("[" + (dutId + 1) + "]无任务");
            }
        }
        // 保存测试详情
        //internal void AddDutDetails(int dutId, List<string> detail)
        //{
        //    // 暂时屏蔽 duts detail
        //    //int uId = DutsLogicalMap.ConventIdToUI(dutId, _groupId);
        //    //foreach(var s in detail)
        //    //{
        //    //    if(_teamViewModel.DutsDetail[uId].Length>0)
        //    //    {
        //    //        _teamViewModel.DutsDetail[uId] += "\r\n";
        //    //    }
        //    //    _teamViewModel.DutsDetail[uId] += ">";
        //    //    _teamViewModel.DutsDetail[uId] += "[" + DateTime.Now.ToString("HH:mm:ss") + "]";
        //    //    _teamViewModel.DutsDetail[uId] += s;
        //    //}
        //}

        internal void ResetDutDetails(int dutId)
        {
            // 暂时屏蔽 duts detail
            //int uId = DutsLogicalMap.ConventIdToUI(dutId, _groupId);
            //_teamViewModel.DutsDetail[uId] = "";
        }
        // 保存完成记录
        //internal void SetDutTestResult(int dutId, string time, string detail, ushort errorCode)
        //{
        //    lock (_lockObj)
        //    {
        //        _DutFinishRecord[dutId] = new Tuple<string, string, ushort>(time, detail, errorCode);
        //    }
        //}
        //internal string GetDutTestResult(int dutId, bool needErrCode)
        //{
        //    string record = null;
        //    lock (_lockObj)
        //    {
        //        record = _DutFinishRecord[dutId].Item1;
        //        if (needErrCode)
        //        {
        //            record += (" 状态码:" + _DutFinishRecord[dutId].Item3.ToString("X2"));
        //        }
        //        if (_DutFinishRecord[dutId].Item2.Length > 0)
        //        {
        //            record += Environment.NewLine;
        //            record += _DutFinishRecord[dutId].Item2;
        //        }
        //    }
        //    return record;
        //}

    }

}
