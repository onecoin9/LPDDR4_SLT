using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Hsg.Common;
using Hsg.BLL.config;

namespace Hsg.BLL.Model
{
    public partial class BSController
    {
        // private IUpdateUILayer<UIState> _iUpdateUILayer;
        private IUIAppendLog _iUIAppendLog;
        private void AppendLogToUi(string log, LOG_TYPE type)
        {
            if (_iUIAppendLog != null)
            {
                _iUIAppendLog(log, type);
            }
        }
        public void BindUIUpdate(IUIAppendLog appendLog)
        {
            _iUIAppendLog += appendLog;
        }
        public void UnbindUi()
        {
            _iUIAppendLog = null;
        }

        public void OnBSTeamStageChange(int teamId, TestStage stage)
        {
            //Hlog.E("DoActionStatusCheck  @@@@@@@");
            int online = 0;
            int testCount = 0;
            if (stage == TestStage.ST_TEST_FAIL
                || stage == TestStage.ST_TEST_SUCCESS
                || stage == TestStage.ST_TEST_TIMEOUT)
            {
                CalculateFinishBinCount(teamId);
                SendTestFinshReporReq(teamId);
            }

            lock (_opLock)
            {
                //检查在线team
                for (int i = 0; i < _teamList.Count; i++)
                {
                    if (_teamList[i].Stage >= TestStage.ST_READY)
                    {
                        online++;
                    }
                    if (_teamList[i].Stage == TestStage.ST_TESTING)
                    {
                        testCount++;
                    }
                }
                if (stage > TestStage.ST_TESTING)
                {
                    //   List<TestStage> dutStates = _teamList[teamId].uiState.dutStates;
                    for (int i = 0; i < _stateFailStatistics.Length; i++) // 统计所有失败的记录
                    {
                        _stateFailStatistics[i] += _teamList[teamId].GetStageFailCount(i);
                    }

                    for (int i = 0; i < BSTeamConfig.DUTS_COUNT; i++)
                    {
                        TestStage dutStage = _teamList[teamId].GetDutStage(i);
                        if (dutStage > TestStage.ST_TESTING)
                        {
                            lock (_opLock)
                            {
                                if (dutStage == TestStage.ST_TEST_SUCCESS)
                                {
                                    _viewModel.PassDutNum++;
                                }
                                _viewModel.TestDutNum++;
                            }
                        }
                    }
                }
                if (online == SysConfig.DEV_NUM && CurState == BSCStatus.ST_IDLE && _viewModel.OnlineBoard != online)
                {
                    PostEventAsync(BSCEvent.EVT_ALL_TEAM_READY);
                }
                _viewModel.OnlineBoard = online;
                // 检查测试中的team
                _viewModel.TestingTeamNum = testCount;
            }
        }

        public void BindTeamUIUpdate(int teamId)
        {
            if (teamId >= 0 && teamId < _teamList.Count)
            {
                _teamList[teamId].BindUIUpdate(AppendLogToUi);
            }
        }

        private void CalculateFinishBinCount(int teamId)
        {
            byte[] binNumbers = _teamList[teamId].GetDutsBinCode();/*ConventErrorCodeToBinNumber(_teamList[teamId].GetDutsErrorCode());*/
            for (int i = 0; i < binNumbers.Length; i++)
            {
                int binId = binNumbers[i];
                if (binId > 0 && binId <= SysConfig.MAX_BIN_COUNT)
                {
                    lock (_opLock)
                    {
                        _binRecord[binId - 1]++;
                    }
                }
            }
        }
    }
}
