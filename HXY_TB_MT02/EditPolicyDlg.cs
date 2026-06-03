using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using Hsg.BLL;
using System.IO;
using Hsg.Common.ADO;
using Hsg.Common;

namespace Hsg.View
{
    public enum PolicyOperator
    {
        NEW,
        EDIT,
        VIEW,
    }
    public partial class EditPolicyDlg : Form
    {
        private byte _tempState = (byte)TempState.TmpHight;// 温控状况
        private PolicyOperator _operator;
        private string _itemPath;
        public string EditFilePath;
        public EditPolicyDlg(PolicyOperator op = PolicyOperator.NEW, string itemPath = "")
        {
            bool subCtr_enable = true;
            InitializeComponent();

            _operator = op;
            _itemPath = itemPath;
            EditFilePath = itemPath;
            string subPath = itemPath.Length > 0 ? Path.GetDirectoryName(itemPath) : "";
            txt_sub_path.Text = subPath;

            if (op == PolicyOperator.NEW)
            {
                AddPolicyItem();
                UpdateItemIndex();
            }
            else
            {
                string errorMsg = "";
                if (!LoadPolicyContent(itemPath, ref errorMsg))
                {
                    MessageBox.Show("文件载入失败" + errorMsg);
                }
                //m_cbx_subPath.Enabled = false;
                //m_btn_new_path.Enabled = false;
            }
            if (op == PolicyOperator.VIEW)
            {
                subCtr_enable = false;
            }
            btn_save.Enabled = subCtr_enable;
            txt_policy_name.Enabled = subCtr_enable;
            rbt_hight_tmp.Enabled = subCtr_enable;
            rbt_mixture_tmp.Enabled = subCtr_enable;
            rbt_normal_tmp.Enabled = subCtr_enable;
            m_btn_select_dir.Enabled = subCtr_enable;
        }

        private List<string> SCanFolder()
        {
            List<string> subFolders = new List<string>();
            string parentFolderPath = SysConfig.PolicyFolderPath;

            try
            {
                // 获取父文件夹下的一级子目录
                DirectoryInfo parentDirectory = new DirectoryInfo(parentFolderPath);
                DirectoryInfo[] subDirectories = parentDirectory.GetDirectories();

                //Console.WriteLine($"在文件夹 '{parentFolderPath}' 下的一级子目录有：");
                foreach (DirectoryInfo dir in subDirectories)
                {
                    //Console.WriteLine(dir.FullName);
                    subFolders.Add(dir.Name);
                }
            }
            catch (DirectoryNotFoundException)
            {
                Console.WriteLine($"指定的文件夹 '{parentFolderPath}' 不存在。");
            }
            catch (UnauthorizedAccessException)
            {
                Console.WriteLine($"没有权限访问指定的文件夹 '{parentFolderPath}'。");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"发生错误：{ex.Message}");
            }
            return subFolders;
        }
        private void AddPolicyItem(PolicyMember valueMember = null)

        {
            var policyItem = new PolicyControl();
            policyItem.AddClicked += OnAddClicked;

            policyItem.DeleteClicked += OnDeleteClicked;
            if (valueMember != null)
            {
                policyItem.LoadFromObject(valueMember);
            }
            if (_operator == PolicyOperator.VIEW)
            {
                policyItem.Enabled = false;
            }
            policyItem.SetPolicyTempState((TempState)_tempState);
            m_pal_policy_list.Controls.Add(policyItem);
        }

        private void OnAddClicked(object sender, EventArgs e)

        {
            // 在当前位置之后插入新的UserControl

            var currentItem = (PolicyControl)sender;

            int index = m_pal_policy_list.Controls.GetChildIndex(currentItem);

            var newItem = new PolicyControl();

            newItem.AddClicked += OnAddClicked;

            newItem.DeleteClicked += OnDeleteClicked;
            newItem.SetPolicyTempState((TempState)_tempState);
            m_pal_policy_list.Controls.Add(newItem);

            // 可能需要调整索引，或者使用Insert方法

            m_pal_policy_list.Controls.SetChildIndex(newItem, index + 1);
            UpdateItemIndex();

        }
        private void UpdateItemIndex()
        {
            for (int i = 0; i < m_pal_policy_list.Controls.Count; i++)
            {
                PolicyControl item = (PolicyControl)m_pal_policy_list.Controls[i];
                item.ID = (i + 1).ToString();
            }
        }

        private void OnDeleteClicked(object sender, EventArgs e)

        {
            var itemToRemove = (PolicyControl)sender;

            itemToRemove.AddClicked -= OnAddClicked;

            itemToRemove.DeleteClicked -= OnDeleteClicked;

            m_pal_policy_list.Controls.Remove(itemToRemove);

            itemToRemove.Dispose();
        }

        private void btn_save_Click(object sender, EventArgs e)
        {
            char[] badChars = Path.GetInvalidFileNameChars();
            if (txt_policy_name.TextLength == 0)
            {
                MessageBox.Show("文件名不能为可空");
                return;
            }
            char[] nameArray = txt_policy_name.Text.ToCharArray();
            if (nameArray.Length > 255)
            {
                MessageBox.Show("文件名称超出最大长度");
                return;
            }

            if (m_pal_policy_list.Controls.Count == 0)
            {
                MessageBox.Show("当前不存在配方内容");
                return;
            }
            string invalidStr = "";
            foreach (var v in nameArray)
            {
                if (badChars.Contains(v))
                {

                    invalidStr += v;
                }
            }
            if (invalidStr.Length > 0)
            {
                MessageBox.Show($"存在不合法字符{invalidStr}");
                return;
            }
            string policyPath = txt_policy_name.Text;
            policyPath = Path.Combine(txt_sub_path.Text, txt_policy_name.Text);
            string fullPath = Path.Combine(SysConfig.PolicyFolderPath, policyPath) + SysConfig.PolicyFileExtName;
            if (File.Exists(fullPath))
            {
                if (MessageBox.Show("检查到已有文件,替换原有文件?", "冲突提醒", MessageBoxButtons.OKCancel) != DialogResult.OK)
                {
                    return;
                }
            }

            for (int i = 0; i < m_pal_policy_list.Controls.Count; i++)
            {
                PolicyControl item = (PolicyControl)m_pal_policy_list.Controls[i];
                string errorMsg = "";
                if (!item.ContentCheck(ref errorMsg))
                {
                    MessageBox.Show(errorMsg);
                    return;
                }
            }

            PolicyFile policy = new PolicyFile();
            for (int i = 0; i < m_pal_policy_list.Controls.Count; i++)
            {
                PolicyControl item = (PolicyControl)m_pal_policy_list.Controls[i];
                PolicyMember member = new PolicyMember();
                item.ToStoreObject(ref member);
                policy.AddMember(member);
            }
            if (rbt_hight_tmp.Checked)
            {
                policy.TempFlag = (byte)TempState.TmpHight;
            }
            else if (rbt_mixture_tmp.Checked)
            {
                policy.TempFlag = (byte)TempState.TmpMixture;
            }
            else
            {
                policy.TempFlag = (byte)TempState.TmpNormal;
            }
            //string namePath = Path.Combine(SysConfig.PolicyFolderPath, txt_policy_name.Text) + SysConfig.PolicyFileExtName;
            try
            {
                policy.SaveToFile(fullPath);
                MessageBox.Show("保存成功");
                DialogResult = DialogResult.OK;
                EditFilePath = policyPath;
                Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show("保存配置失败" + ex);
            }

        }

        private void OnTempStateChange(object sender, EventArgs e)
        {
            if (rbt_hight_tmp.Checked)
            {
                _tempState = (byte)TempState.TmpHight;
            }
            else if (rbt_mixture_tmp.Checked)
            {
                _tempState = (byte)TempState.TmpMixture;
            }
            else
            {
                _tempState = (byte)TempState.TmpNormal;
            }
            foreach (var v in m_pal_policy_list.Controls)
            {
                PolicyControl control = v as PolicyControl;
                control.SetPolicyTempState((TempState)_tempState);
            }
        }

        private bool LoadPolicyContent(string fileName, ref string errorMsg)
        {
            string fullPath = Path.Combine(SysConfig.PolicyFolderPath, fileName) + SysConfig.PolicyFileExtName;
            if (!File.Exists(fullPath))
            {
                errorMsg = "文件不存在";
                return false;
            }

            PolicyFile policy = PolicyFile.Deserialize(fullPath, ref errorMsg);
            if (policy == null)
            {
                return false;
            }
            if (policy.TempFlag == (byte)TempState.TmpHight)
            {
                rbt_hight_tmp.Checked = true;
                rbt_normal_tmp.Checked = false;
                rbt_mixture_tmp.Checked = false;
            }
            else if (policy.TempFlag == (byte)TempState.TmpMixture)
            {
                rbt_mixture_tmp.Checked = true;
                rbt_hight_tmp.Checked = false;
                rbt_normal_tmp.Checked = false;
            }
            else
            {
                rbt_hight_tmp.Checked = false;
                rbt_normal_tmp.Checked = true;
                rbt_mixture_tmp.Checked = false;
            }
            _tempState = (byte)policy.TempFlag;
            if (policy.MemberList.Count > 0)
            {
                for (int i = 0; i < policy.MemberList.Count; i++)
                {

                    AddPolicyItem(policy.MemberList[i]);
                }
            }
            txt_policy_name.Text = Path.GetFileName(fileName);
            UpdateItemIndex();

            return true;
        }

        private void OnBtnCreateDirClick(object sender, EventArgs e)
        {

        }

        private void OnBtnSelectDirClick(object sender, EventArgs e)
        {
            using (FolderBrowserDialog folderBrowserDialog = new FolderBrowserDialog())
            {
                string policyFolderPath = Path.Combine(Application.StartupPath, SysConfig.PolicyFolderPath);
                // 设置对话框的标题（描述）
                folderBrowserDialog.Description = "请选择文件夹";
                // 设置初始目录（可选）
                folderBrowserDialog.SelectedPath = policyFolderPath;
                // 显示对话框，并检查用户是否点击了“确定”
                if (folderBrowserDialog.ShowDialog() == DialogResult.OK)
                {
                    // 获取用户选择的文件夹路径
                    string selectedPath = folderBrowserDialog.SelectedPath;
                    // 在这里使用selectedPath，比如显示在文本框里
                    if(policyFolderPath == selectedPath)
                    {
                        txt_sub_path.Text = "";
                    }
                    else if (selectedPath.Contains(policyFolderPath + "\\"))
                    {
                        string relativePath = Tools.GetRelativePath(policyFolderPath, selectedPath);
                        txt_sub_path.Text = relativePath;
                    }
                    else
                    {
                        MessageBox.Show("不支持默认文件夹以外路径的下的子路径");
                    }
                }
            }
        }
    }
}
