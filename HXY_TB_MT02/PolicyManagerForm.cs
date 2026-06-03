using Hsg.BLL;
using Hsg.Common;
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
    public partial class PolicyManagerForm : Form
    {
        //SysConfig _sysconfig;
        public PolicyManagerForm()
        {
           // _sysconfig = SysConfig.GetInstance();
            InitializeComponent();
            //ScanPolicyFile();
        }

        private void OnBtnEditClick(object sender, EventArgs e)
        {
            if (m_txt_policy_path.Text.Length <= 0)
            {
                MessageBox.Show("请选择有效的操作对象");
                return;
            }
            string selectItem = m_txt_policy_path.Text;
            EditPolicyDlg dlg = new EditPolicyDlg(PolicyOperator.EDIT, selectItem);
            dlg.ShowDialog();
        }

        private void OnBtnAddClick(object sender, EventArgs e)
        {
            EditPolicyDlg dlg = new EditPolicyDlg(PolicyOperator.NEW);
            if(dlg.ShowDialog() == DialogResult.OK)
            {
                m_txt_policy_path.Text = dlg.EditFilePath;
            }
        }

        private void OnBtnDeleteClick(object sender, EventArgs e)
        {
            if (m_txt_policy_path.Text.Length <= 0)
            {
                MessageBox.Show("请选择有效的操作对象");
                return;
            }
            if (MessageBox.Show("确认删除文件:" + m_txt_policy_path.Text, "确认", MessageBoxButtons.OKCancel) == DialogResult.OK)
            {
                string filePath = Path.Combine(SysConfig.PolicyFolderPath, m_txt_policy_path.Text) + SysConfig.PolicyFileExtName;
                File.Delete(filePath);
                MessageBox.Show("操作成功");
                m_txt_policy_path.Text = "";
            }
        }
        //private void ScanPolicyFile()
        //{
        //    string[] policyFileNameList = _sysconfig.GetPolicyFileNameList();
        //    int selectIndex = -1;
        //    cbx_policy_list.Items.Clear();
        //    foreach (var v in policyFileNameList)
        //    {
        //        cbx_policy_list.Items.Add(v);
        //        if (_selectPolicyName.Length >0 && v == _selectPolicyName)
        //        {
        //            selectIndex = cbx_policy_list.Items.Count - 1;
        //        }
        //    }
        //    cbx_policy_list.SelectedIndex = selectIndex;
        //}

        private void OnBtnViewClick(object sender, EventArgs e)
        {
            if (m_txt_policy_path.Text.Length <= 0)
            {
                MessageBox.Show("请选择有效的操作对象");
                return;
            }
            string selectItem = m_txt_policy_path.Text;
            EditPolicyDlg dlg = new EditPolicyDlg(PolicyOperator.VIEW, selectItem);
            dlg.ShowDialog();
        }

        private void OnSelectBtnClick(object sender, EventArgs e)
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

        private void m_txt_policy_path_TextChanged(object sender, EventArgs e)
        {

        }
    }
}
