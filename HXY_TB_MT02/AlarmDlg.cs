using Hsg.BLL.Model;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Hsg.View
{
    public partial class AlarmDlg : Form
    {
        private BindingSource bindingSource = new BindingSource();
        private BSController _bsControl;
        private int _teamId;
        public AlarmDlg(BSController bsControl, TestTeamlView viewModel, int teamId)
        {
            InitializeComponent();
            this.Text = "测试组" + teamId.ToString() + "警告处理";
            bindingSource.DataSource = viewModel;
            m_lab_alarm.Text = viewModel.AlarmMsg;
            _bsControl = bsControl;
            _teamId = teamId;
        }

        private void m_btn_retry_Click(object sender, EventArgs e)
        {
            _bsControl.OnRetryAbnormalTest(_teamId -1);
            Close();
        }

        private void m_btn_cancel_Click(object sender, EventArgs e)
        {
            Close();
        }
    }
}
