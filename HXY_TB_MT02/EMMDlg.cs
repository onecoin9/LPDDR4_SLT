using Hsg.BLL;
using Hsg.Common.ADO;
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
     enum OptionType
    {
        None,
        Query_last,
        Query_last_all,
        Query_abnormal,
        Query_abnormal_all
    };
    public partial class EMMDlg : Form
    {
        private TeamStateManager _dutStateMgr;
        private OptionType _lastOption = OptionType.None;
        public EMMDlg()
        {
            _dutStateMgr = TeamStateManager.GetInstance();
            InitializeComponent();
            m_lv_dut_abnormal.View = System.Windows.Forms.View.Details;
            m_lv_dut_abnormal.FullRowSelect = true;

            for (int i = 0; i < SysConfig.DEV_NUM; i++)
            {
                int no = i + 1;
                m_cbx_box_no.Items.Add(no.ToString("D2"));
            }
        }

        private void LoadTeamMemberLastStates(int boxId)
        {
            ushort[] loadState = Array.Empty<ushort>();
            ushort[] continueCount = Array.Empty<ushort>();
            if (_dutStateMgr.LoadTeamMemberLastStateCode(boxId, ref loadState, ref continueCount))
            {
                for (int i = 0; i < loadState.Length; i++)
                {
                    int dutNo = i;
                    if (loadState[i] == 0)
                    {
                        continue;
                    }
                    if (m_cbx_filter_up_two.Checked)
                    {
                        if (continueCount[i] < 2)
                        {
                            continue;
                        }
                    }
                    if (m_cbx_filter_up_three.Checked)
                    {
                        if (continueCount[i] < 3)
                        {
                            continue;
                        }
                    }
                    ListViewItem item = null;
                    item = new ListViewItem((boxId + 1).ToString("D2"));
                    switch (i)
                    {
                        case (int)StateRecordIndex.TempCtr:
                            item.SubItems.Add(dutNo.ToString("TC"));
                            break;
                        default:
                            dutNo = i - (int)StateRecordIndex.DutIndexBegin + 1;
                            item.SubItems.Add(dutNo.ToString("D2"));
                            break;
                    }
                    item.SubItems.Add(loadState[i].ToString("X2"));
                    item.SubItems.Add(continueCount[i].ToString("D"));
                    string descript = DutMaster.ParseStateCodeMsg((ushort)loadState[i]);
                    item.SubItems.Add(descript);
                    m_lv_dut_abnormal.Items.Add(item);
                }
            }
        }
        private void LoadTeamMemberEvtAbnormal(int boxId)
        {
            //short[] loadState = Array.Empty<short>();
            //short[] countArray = Array.Empty<short>();
            //string[] extraInfo = Array.Empty<string>();
            List<AbnormalRecord> readRecord = new List<AbnormalRecord>();
            if (_dutStateMgr.LoadTeamMemberEvtAbnormalRecord(boxId, ref readRecord))
            {
                for (int i = 0; i < readRecord.Count; i++)
                {
                    int dutNo = readRecord[i].id;

                    ListViewItem item = null;
                    item = new ListViewItem((boxId + 1).ToString("D2"));
                    switch (dutNo)
                    {
                        case (int)AbnormalRecordIndex.TempCtr:
                            item.SubItems.Add("TC");
                            break;
                        case (int)AbnormalRecordIndex.CommunicateBoard01:
                            item.SubItems.Add("TB1");
                            break;
                        case (int)AbnormalRecordIndex.CommunicateBoard02:
                            item.SubItems.Add("TB2");
                            break;
                        default:
                            dutNo = dutNo - (int)AbnormalRecordIndex.DutIndexBegin + 1;
                            item.SubItems.Add(dutNo.ToString("D2"));
                            break;
                    }
                    ushort code = (ushort)readRecord[i].code;
                    item.SubItems.Add(code.ToString("X2"));
                    item.SubItems.Add(readRecord[i].count.ToString("D"));
                    string descript = DutMaster.ParseStateCodeMsg((ushort)readRecord[i].code);
                    item.SubItems.Add(descript);
                    if (readRecord[i].extra != null)
                    {
                        item.SubItems.Add(readRecord[i].extra);
                    }

                    m_lv_dut_abnormal.Items.Add(item);
                }
            }
        }
        private void ClearTeamMemberEvtAbnormal(int boxId)
        {
            _dutStateMgr.ClearTeamMemberEvtAbnormalRecord(boxId);
        }
        private void m_btn_query_Click(object sender, EventArgs e)
        {
            m_lv_dut_abnormal.Items.Clear();
            m_lv_dut_abnormal.Columns.Clear();
            m_lv_dut_abnormal.Columns.Add("测试盒", 80);
            m_lv_dut_abnormal.Columns.Add("Dut", 60);
            m_lv_dut_abnormal.Columns.Add("错误码", 80);
            m_lv_dut_abnormal.Columns.Add("连续次数", 80);
            m_lv_dut_abnormal.Columns.Add("描述", 300);
            if (m_cbx_box_no.SelectedIndex >= 0)
            {
                int boxId = m_cbx_box_no.SelectedIndex;
                LoadTeamMemberLastStates(boxId);
                _lastOption = OptionType.Query_last;
                return;
            }
            MessageBox.Show("请选择要查询的测试盒编号");
        }

        private void OnBtnQueryAllClick(object sender, EventArgs e)
        {
            m_lv_dut_abnormal.Items.Clear();
            m_lv_dut_abnormal.Columns.Clear();
            m_lv_dut_abnormal.Columns.Add("测试盒", 80);
            m_lv_dut_abnormal.Columns.Add("Dut", 60);
            m_lv_dut_abnormal.Columns.Add("错误码", 80);
            m_lv_dut_abnormal.Columns.Add("连续次数", 80);
            m_lv_dut_abnormal.Columns.Add("描述", 300);
            for (int i = 0; i < m_cbx_box_no.Items.Count; i++)
            {
                LoadTeamMemberLastStates(i);
            }
            _lastOption = OptionType.Query_last_all;
        }

        private void OnQueryAbnormalClick(object sender, EventArgs e)
        {
            m_lv_dut_abnormal.Items.Clear();
            m_lv_dut_abnormal.Columns.Clear();
            m_lv_dut_abnormal.Columns.Add("测试盒", 80);
            m_lv_dut_abnormal.Columns.Add("组件", 60);
            m_lv_dut_abnormal.Columns.Add("异常码", 80);
            m_lv_dut_abnormal.Columns.Add("次数", 80);
            m_lv_dut_abnormal.Columns.Add("描述", 300);
            m_lv_dut_abnormal.Columns.Add("附加信息", 300);
            if (m_cbx_box_no.SelectedIndex >= 0)
            {
                int boxId = m_cbx_box_no.SelectedIndex;
                LoadTeamMemberEvtAbnormal(boxId);
                _lastOption = OptionType.Query_abnormal;
                return;
            }
            MessageBox.Show("请选择要查询的测试盒编号");
            
        }

        private void OnBtnQueryAllAbnormalClick(object sender, EventArgs e)
        {
            m_lv_dut_abnormal.Items.Clear();
            m_lv_dut_abnormal.Columns.Clear();
            m_lv_dut_abnormal.Columns.Add("测试盒", 80);
            m_lv_dut_abnormal.Columns.Add("组件", 60);
            m_lv_dut_abnormal.Columns.Add("异常码", 80);
            m_lv_dut_abnormal.Columns.Add("次数", 80);
            m_lv_dut_abnormal.Columns.Add("描述", 300);
            m_lv_dut_abnormal.Columns.Add("附加信息", 300);
            for (int i = 0; i < m_cbx_box_no.Items.Count; i++)
            {
                LoadTeamMemberEvtAbnormal(i);
            }
            _lastOption = OptionType.Query_abnormal_all;
        }

        private void OnBtnExportAllClick(object sender, EventArgs e)
        {

        }

        //private void OnBtnClearAbnormalClick(object sender, EventArgs e)
        //{

        //}

        private void m_lv_dut_abnormal_MouseDoubleClick(object sender, MouseEventArgs e)
        {
            //Password pwd = new Password("10086");
            if(_lastOption != OptionType.Query_abnormal && _lastOption != OptionType.Query_abnormal_all)
            {
                return;
            }
            int selectCount = m_lv_dut_abnormal.SelectedItems.Count;
            if (selectCount > 0)
            {
                // 获取选中行的索引
                int selectedIndex = m_lv_dut_abnormal.SelectedItems[0].Index;
                string  selectBox = m_lv_dut_abnormal.Items[selectedIndex].SubItems[0].Text;
                string selectCompontId = m_lv_dut_abnormal.Items[selectedIndex].SubItems[1].Text;
                string abnormalCodeString = m_lv_dut_abnormal.Items[selectedIndex].SubItems[2].Text;
                int componentId = -1;
                int boxId = -1;
                ushort abnormalCode = 0;
                switch(selectCompontId)
                {
                    case "TC":
                        componentId = (int)AbnormalRecordIndex.TempCtr;
                        break;
                    case "TB1":
                        componentId = (int)AbnormalRecordIndex.CommunicateBoard01;
                        break;
                    case "TB2":
                        componentId = (int)AbnormalRecordIndex.CommunicateBoard02;
                        break;
                    default:
                        if(!Int32.TryParse(selectCompontId, out componentId))
                        {
                            componentId = -1;
                        }else
                        {
                            componentId += (int)AbnormalRecordIndex.DutIndexBegin -1;
                        }
                        break;
                }
                abnormalCode = Convert.ToUInt16(abnormalCodeString, 16);
                if(!Int32.TryParse(selectBox, out boxId))
                {
                    boxId = -1;
                }
                if(componentId >=0 && boxId>=1)
                {
                    if(MessageBox.Show("是否删除记录","删除", MessageBoxButtons.YesNo)== DialogResult.Yes)
                    {
                        _dutStateMgr.ClearTeamMemberEvtAbnormalRecord(boxId - 1, componentId,(short)abnormalCode);
                    }else
                    {
                        return;
                    }
                }
               
            }
            else
            {
                MessageBox.Show("未选择有效的记录");
                return;
            }
            if (_lastOption == OptionType.Query_abnormal)
            {
                OnQueryAbnormalClick(sender, e);
            }
            else if(_lastOption == OptionType.Query_abnormal_all)
            {
                OnBtnQueryAllAbnormalClick(sender, e);
            }
        }

        private async void OnBtnClearCurrentAbnormalClick(object sender, EventArgs e)
        {
            if (m_cbx_box_no.SelectedIndex >= 0)
            {
                int boxId = m_cbx_box_no.SelectedIndex;
                Password pwdCheckDlg = new Password("10086");
                pwdCheckDlg.Text = "请输入权限密码";
                DialogResult result = pwdCheckDlg.ShowDialog();
                if (result == DialogResult.Retry)
                {
                    MessageBox.Show("修改密码不正确");
                    return;
                }
                else if (result == DialogResult.Cancel)
                {
                    return;
                }

                await Task.Run(() =>
                {
                    ClearTeamMemberEvtAbnormal(boxId);
                });
                OnQueryAbnormalClick(sender, e);
                return;
            }
            MessageBox.Show("请选择要查询的测试盒编号");
        }

        private async void OnBtnClearAllAbnormalClick(object sender, EventArgs e)
        {
            Password pwdCheckDlg = new Password("10086");
            pwdCheckDlg.Text = "请输入权限密码";
            DialogResult result = pwdCheckDlg.ShowDialog();
            if (result == DialogResult.Retry)
            {
                MessageBox.Show("修改密码不正确");
                return;
            }
            else if (result == DialogResult.Cancel)
            {
                return;
            }
            await Task.Run(() =>
            {
                for (int i = 0; i < m_cbx_box_no.Items.Count; i++)
                {
                    ClearTeamMemberEvtAbnormal(i);
                }
            });
            OnBtnQueryAllAbnormalClick(sender, e);
        }

        private void m_cbx_filter_up_two_CheckedChanged(object sender, EventArgs e)
        {
            if (m_cbx_filter_up_two.Checked)
            {
                m_cbx_filter_up_three.Checked = false;
            }
        }

        private void m_cbx_filter_up_three_CheckedChanged(object sender, EventArgs e)
        {
            if (m_cbx_filter_up_three.Checked)
            {
                m_cbx_filter_up_two.Checked = false;
            }
        }

        private void EMMDlg_Load(object sender, EventArgs e)
        {

        }
    }
}
