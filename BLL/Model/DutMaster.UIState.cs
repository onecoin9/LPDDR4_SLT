using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Hsg.Common;

namespace Hsg.BLL
{
    public partial class DutMaster
    {
        private IUIAppendLog _iUIAppendLog;
        public void AddStageDetail(string detail)
        {
            _detailBuilder.AppendLine($"<< [{DateTime.Now.ToString("HH:mm:ss")}] {detail}");
            //OnUIChange();
        }
        public void ResetStageDetail()
        {
            _detailBuilder?.Clear();
        }
        public void BindUIUpdate(IUIAppendLog appendLog)
        {
            _iUIAppendLog += appendLog;
        }
        private void AppendLogToUi(string log, LOG_TYPE type)
        {
            if (_iUIAppendLog != null)
            {
                _iUIAppendLog(string.Format(@"[{0}]{1}",_instanceId + 1, log), type);
            }
        }
        public void UnbindUi()
        {
            _iUIAppendLog = null;
        }

    }
}
