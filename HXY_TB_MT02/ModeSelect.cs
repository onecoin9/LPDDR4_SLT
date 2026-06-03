using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using Hsg.Common;
using Hsg.BLL;

namespace Hsg.View
{
    public partial class ModeSelect : Form
    {
        public WorkMode SelectedMode;
        public ModeSelect()
        {
            InitializeComponent();
        }

        private void m_btn_offline_mode_Click(object sender, EventArgs e)
        {
            //WorkOrderDlg wOrderDlg = new WorkOrderDlg();
            // wOrderDlg.Show();
            WorkOrderDlg wOrderDlg = new WorkOrderDlg(false);
            if (wOrderDlg.ShowDialog() == DialogResult.OK)
            {
                SelectedMode = WorkMode.OffLine;
                DialogResult = DialogResult.OK;
                Close();
            }
        }

        private void m_btn_debug_mode_Click(object sender, EventArgs e)
        {
            SelectedMode = WorkMode.Debug;
            DialogResult = DialogResult.OK;
            if (MessageBox.Show("是否开启高温", "温控选择", MessageBoxButtons.YesNo) == DialogResult.Yes)
            {
                SysConfig.SetWorkOrderDetail(WorkMode.Debug, "调试", "PRT", 0, "Debug", "Debug", "None", 1);
            }
            else
            {
                SysConfig.SetWorkOrderDetail(WorkMode.Debug, "调试", "PRT", 0, "Debug", "Debug", "None", 0);
            }

            Close();
        }

        private void m_btn_online_mode_Click(object sender, EventArgs e)
        {
            MessageBox.Show("功能开发中,请选择其他模式。");
        }

        private void On_Policy_Manager_Click(object sender, EventArgs e)
        {
            Password pwd = new Password("10086");
            if (pwd.ShowDialog() == DialogResult.OK)
            {
                PolicyManagerForm form = new PolicyManagerForm();
                form.ShowDialog();
            }
        }
    }
}
