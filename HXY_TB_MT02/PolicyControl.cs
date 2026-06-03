using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.IO;
using Hsg.BLL;
using Hsg.BLL.Policy;
using Hsg.Common.ADO;
using Hsg.Common;

namespace Hsg.View
{
    public partial class PolicyControl : UserControl
    {
        public event EventHandler AddClicked;

        public event EventHandler DeleteClicked;
        private PolicyConfig _policyMgr;
        private byte[] _cfgFileData = new byte[0];
        public string ID
        {
            get { return lab_id.Text; }
            set { lab_id.Text = value; }
        }
        public PolicyControl()
        {
            InitializeComponent();
            _policyMgr = PolicyConfig.Instance;
            btn_add.Click += (s, e) => AddClicked?.Invoke(this, e);

            btn_delete.Click += (s, e) => DeleteClicked?.Invoke(this, e);
        }
        public bool ContentCheck(ref string errorMsg)
        {
            if (txt_description.TextLength == 0)
            {
                errorMsg = "描述不能为空";
                return false;
            }
            if (txt_config_name.TextLength == 0)
            {
                errorMsg = "描述不能为空";
                return false;
            }
            if (nud_timeoutMin.Value == 0)
            {
                errorMsg = "超时时间不能为0";
                return false;
            }

            if (nud_frequency.Value == 0)
            {
                errorMsg = "执行次数请设置非0值";
                return false;
            }
            if (nud_frequency.Value < nud_allow_fail.Value)
            {
                errorMsg = "执行次数不能小于最大失败次数";
                return false;
            }

            return true;
        }

        private void OnSelectCfgFileClick(object sender, EventArgs e)
        {
            OpenFileDialog ofile = new OpenFileDialog();
            ofile.Title = "选择配置文件";
            ofile.InitialDirectory = Application.StartupPath;
            ofile.Filter = PolicyConfig.GetPolicyFileFilter();
            if (ofile.ShowDialog() == DialogResult.OK)
            {
                string filePath = ofile.FileName;
                PolicyCfgBase policy = PolicyConfig.LoadPolicyFile(filePath);
                if (policy == null)
                {
                    MessageBox.Show("文件内容错误");
                    return;
                }
                else
                {
                    using (FileStream fs = new FileStream(filePath, FileMode.Open))
                    {
                        _cfgFileData = new byte[fs.Length];
                        if (fs.Read(_cfgFileData, 0, (int)fs.Length) != fs.Length)
                        {
                            MessageBox.Show("读取配置文件失败");
                            return;
                        }
                    }
                    if (policy.IsEncrypt())
                    {
                        nud_timeoutMin.Value = policy.GetTimeout();
                        nud_timeoutMin.Enabled = false;
                    }
                    else
                    {
                        nud_timeoutMin.Enabled = true;
                    }
                    txt_config_name.Text = policy.GetFileName();
                }
            }
        }

        public bool ToStoreObject(ref PolicyMember member)
        {
            member.param.CfgFileName = txt_config_name.Text;
            member.param.Description = txt_description.Text;
            member.param.ExcuteFrequency = (UInt32)nud_frequency.Value;
            member.param.RepeatMaxFail = (UInt32)nud_allow_fail.Value;
            member.param.RepeatOptimization = cbx_result_optimization.Checked;
            member.param.TimeoutMinute = (UInt32)nud_timeoutMin.Value;
            member.param.TempFlag = (byte)(rbt_hight_tmp.Checked ? TempState.TmpHight : TempState.TmpNormal);
            member.cfgFileBytes = _cfgFileData;
            return true;
        }
        public void SetPolicyTempState(TempState tempState)
        {
            switch (tempState)
            {
                case TempState.TmpHight:
                    rbt_hight_tmp.Checked = true;
                    rbt_normal_tmp.Checked = false;
                    rbt_hight_tmp.Enabled = false;
                    rbt_normal_tmp.Enabled = false;
                    break;
                case TempState.TmpNormal:
                    rbt_hight_tmp.Checked = false;
                    rbt_normal_tmp.Checked = true;
                    rbt_hight_tmp.Enabled = false;
                    rbt_normal_tmp.Enabled = false;
                    break;
                case TempState.TmpMixture:
                    rbt_hight_tmp.Enabled = true;
                    rbt_normal_tmp.Enabled = true;
                    break;
                    /// 低温暂时未处理
            }
        }
        public bool LoadFromObject(PolicyMember member)
        {
            txt_config_name.Text = member.param.CfgFileName;
            txt_description.Text = member.param.Description;
            nud_frequency.Value = member.param.ExcuteFrequency;
            nud_allow_fail.Value = member.param.RepeatMaxFail;
            cbx_result_optimization.Checked = member.param.RepeatOptimization;
            nud_timeoutMin.Value = member.param.TimeoutMinute;
            if (member.param.TempFlag == (byte)TempState.TmpHight)
            {
                rbt_hight_tmp.Checked = true;
            }
            else
            {
                rbt_normal_tmp.Checked = true;
            }
            _cfgFileData = member.cfgFileBytes;
            if (_policyMgr.CheckPolicyFileIsEncry(member.param.CfgFileName))
            {
                nud_timeoutMin.Enabled = false;
            }
            else
            {
                nud_timeoutMin.Enabled = true;
            }
            return true;
        }
    }
}
