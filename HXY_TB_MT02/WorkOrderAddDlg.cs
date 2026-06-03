using Hsg.BLL;
using Hsg.Common;
using Hsg.Common.ADO;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Hsg.View
{
    public partial class WorkOrderAddDlg : Form
    {
        private DBHandler _dbHandler;
        private SysConfig _config;
        private PolicyConfig _policyMgr;
        private DataTable _workStagesTable;
        public WorkOrderAddDlg()
        {
            InitializeComponent();
            _dbHandler = DBHandler.Instance;
            _config = SysConfig.GetInstance();
            _policyMgr = PolicyConfig.Instance;
            DataSet workStages = _dbHandler.QueryWorkStageFromTable();
            if (workStages != null && workStages.Tables.Count > 0)
            {
                _workStagesTable = workStages.Tables[0];
                m_cbx_stage.DataSource = _workStagesTable;
                m_cbx_stage.DisplayMember = "description";
            }
            m_txb_materialNo.MaxLength = DBTableColumn.MaterialNo.size;
            m_txb_orderNo.MaxLength = DBTableColumn.OrderNo.size;
        }

        private void m_btn_ok_Click(object sender, EventArgs e)
        {
            if (m_txb_materialNo.Text.Length == 0)
            {
                MessageBox.Show("无料编号不能为空");
                return;
            }
            if (m_txb_orderNo.Text.Length == 0)
            {
                MessageBox.Show("订单编号不能为空");
                return;
            }

            if (m_cbx_stage.SelectedIndex < 0)
            {
                MessageBox.Show("请选择当前工序");
                return;
            }
            if (m_txt_policy_path.Text.Length < 0)
            {
                MessageBox.Show("请选择有效的测试策略");
                return;
            }

            string workOrderNo = "";
            string workStageId = "0";
            int selectIndex = m_cbx_stage.SelectedIndex;
            DataRow row = _workStagesTable.Rows[selectIndex];
            workOrderNo += row["name"].ToString();
            //workOrderNo += DateTime.Now.ToString("-yyyy_MM_dd");
            workStageId = row["id"].ToString();


            string errorMsg = "";
            string formulaName = m_txt_policy_path.Text;
            string formulaPath = Path.Combine(SysConfig.PolicyFolderPath, formulaName) + SysConfig.PolicyFileExtName;
            PolicyFile obj = PolicyFile.Deserialize(formulaPath, ref errorMsg);
            if (obj == null)
            {
                MessageBox.Show("读取配置文件失败");
                return;
            }

            if (!_dbHandler.InsertRecordToWorkOrderTable(m_txb_orderNo.Text, m_txb_materialNo.Text, workOrderNo, int.Parse(workStageId), formulaName, (byte)obj.TempFlag))
            {
                MessageBox.Show("添加失败");
            }
            else
            {
                DialogResult = DialogResult.OK;
                Close();
            }

        }

        private void m_btn_cancel_Click(object sender, EventArgs e)
        {
            Close();
        }

        private void OnPolicySelectBtnClick(object sender, EventArgs e)
        {
            string policyFolderPath = Path.Combine(Application.StartupPath, SysConfig.PolicyFolderPath);
            OpenFileDialog ofile = new OpenFileDialog();
            ofile.Title = "选择配置文件";
            ofile.InitialDirectory = policyFolderPath;
            ofile.Filter = SysConfig.PolicyFileFilter;
            ofile.RestoreDirectory = true;
            if (ofile.ShowDialog() == DialogResult.OK)
            {
                if (ofile.FileName.Contains(policyFolderPath))
                {
                    string relativePath = Tools.GetRelativePath(policyFolderPath, ofile.FileName);
                    string extName = Path.GetExtension(ofile.FileName);
                    m_txt_policy_path.Text = relativePath.Substring(0, relativePath.Length - extName.Length);
                }
                else
                {
                    MessageBox.Show("不支持默认文件夹以外路径的文件");
                }
            }
        }
    }
}
