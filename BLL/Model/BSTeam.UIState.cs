using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Hsg.BLL.config;
using Hsg.Common;

namespace Hsg.BLL.Model
{
    public delegate void IUpdateTeamDetail(List<string> stageDetails);
    public partial class BSTeam
    {
        //private IUpdateUILayer<UIState> _iUpdateUILayer;
        private IUIAppendLog _iUiAppendLog;
        private readonly Object _detailLock = new object();
        private void AppendLogToUi(string log, LOG_TYPE type)
        {
            if (_iUiAppendLog != null)
            {
                _iUiAppendLog(string.Format(@"[测试组{0}] {1}", _instanceId + 1, log), type);
            }
        }

        private void ClearLogToDetail()
        {
            lock(_detailLock)
            {
                if (_viewModel.TeamDetail != null)
                {
                    _viewModel.TeamDetail.Clear();
                }
            }
        }
        private void AppendLogToDetil(string log, LOG_TYPE type)
        {
            // uiState.AddStageDetail(log);
            
                lock(_detailLock)
                {
                    if (_viewModel.TeamDetail != null)
                    {
                        _viewModel.TeamDetail.AppendLine($"<< [{DateTime.Now.ToString("HH:mm:ss")}] {log}");
                    }
                }
        }
        //private void AppendLogToUiSimple(string log, LOG_TYPE type)
        //{
        //    if (_iUiAppendLog != null)
        //    {
        //        _iUiAppendLog(string.Format(@"[测试组{0}] {1}", _instanceId + 1, log), type);
        //    }
        //}
        public void BindUIUpdate(IUIAppendLog appendLog)
        {
            _iUiAppendLog += appendLog;
        }
        public void UnbindUi()
        {
            _iUiAppendLog = null;
        }
    }
}
