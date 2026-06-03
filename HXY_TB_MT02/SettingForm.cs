using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Hsg.BLL;
using Hsg.Common;
using System.Globalization;
using System.Threading.Tasks;
using Hsg.BLL.Model;

namespace Hsg.View
{

    public partial class SettingForm : Form
    {
        private SysConfig _config;
        private int _firstIOSelectIndex;
        private bool _debugMode;
        private bool _rebootFlag;
        private bool _bAdminRole;
        BSController _bsControl;

        public bool RebootFlag//修改是否需要重启生效
        {
            get { return _rebootFlag; }
        }

        [DllImport("user32.dll")]
        private static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        public static extern int SendMessage(IntPtr hWnd, int msg, int wParam, int lParam);

        [DllImport("user32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
        const uint SWP_NOSIZE = 0x1;
        const uint SWP_NOMOVE = 0x2;
        const uint SWP_SHOWWINDOW = 0x40;
        public SettingForm( BSController bsController)
        {
            _config = SysConfig.GetInstance();
            _firstIOSelectIndex = 0;
            _bAdminRole = false;
            _bsControl = bsController;
            InitializeComponent();
        }

        public void SetConfigMode(bool configMode)
        {
            _debugMode = configMode;
            _bAdminRole = _debugMode;
        }



        private void SettingForm_Load(object sender, EventArgs e)
        {
            /// 
            int margin_left = 20;
            int margin_top = 20;

            for (int i = 0; i < SysConfig.DEV_NUM; i++)
            {
                Label labText = new Label();
                int id = i + 1;
                int teamId = i + 1;
                labText.Location = new Point(margin_left, i * 40 + margin_top);
                labText.Text = "测试" + teamId.ToString("D2") + "A:";
                //labText.Size = new Size( 116,19);
                TextBox textBox = new TextBox();
                textBox.Location = new Point(margin_left + 100, i * 40 + margin_top);
                textBox.Width = 180;
                if (_config.GroupAIp.GetCount() > i)
                {
                    textBox.Text = _config.GroupAIp.GetItemValue(i);
                }
                textBox.Name = "txt" + id;
                m_pal_ip_list.Controls.Add(labText);
                m_pal_ip_list.Controls.Add(textBox);

            }

            for (int i = 0; i < SysConfig.DEV_NUM; i++)
            {
                Label labText = new Label();
                int teamId = i + 1;
                int id = teamId + SysConfig.DEV_NUM;
                labText.Location = new Point(margin_left + 350, i * 40 + margin_top);
                labText.Text = "测试" + teamId.ToString("D2") + "B:";

                TextBox textBox = new TextBox();
                textBox.Width = 180;
                textBox.Location = new Point(margin_left + 350 + 100, i * 40 + margin_top);
                textBox.Name = "txt" + id;

                if (_config.GroupBIp.GetCount() > i)
                {
                    textBox.Text = _config.GroupBIp.GetItemValue(i);
                }
                m_pal_ip_list.Controls.Add(labText);
                m_pal_ip_list.Controls.Add(textBox);
            }

            /// 
            m_txt_dest_ip.Text = _config.DestIp.Value;
            m_nud_dest_port.Value = Int32.Parse(_config.DestPort.Value);
            //
            //string[] policyNames = _config.GetPolicyFileNameList();
            // foreach (var v in policyNames)
            // {
            //     m_cbx_policy_list.Items.Add(v);
            //     if(v == _config.TestPolicyPath)
            //     {
            //         m_cbx_policy_list.SelectedIndex = m_cbx_policy_list.Items.Count - 1;
            //     }
            // }
            m_txt_config_path.Text = _config.TestPolicyPath;

            if (!_debugMode)
            {
                m_txt_config_path.Enabled = false;
            }

            m_cbx_selected_io.Items.Add("无操作");
            m_cbx_selected_io.Items.Add("测试板开机");
            if (_debugMode)
            {
                m_cbx_selected_io.Items.Add("测试板进入下载模式");
            }
            UInt16 ctrIOGroup = (UInt16)EIOGroup.SWITCH_GROUP_INVALID;
            UInt16.TryParse(_config.IOCtrAId.Value, out ctrIOGroup);
            if (ctrIOGroup >= (UInt16)EIOGroup.SWITCH_GROUP_NUM || ctrIOGroup == 0)
            {
                ctrIOGroup = (UInt16)EIOGroup.SWITCH_GROUP_INVALID;
            }

            if (ctrIOGroup < m_cbx_selected_io.Items.Count)
            {
                m_cbx_selected_io.SelectedIndex = ctrIOGroup;
            }
            else
            {
                m_cbx_selected_io.SelectedIndex = 0;
            }
            m_nud_control_batch.Maximum = SysConfig.PORT_NUM;

            int lineValue = 8;
            Int32.TryParse(_config.IOCtrBatch.Value, out lineValue);
            m_nud_control_batch.Value = lineValue;

            _firstIOSelectIndex = m_cbx_selected_io.SelectedIndex;
            int ctrIOStartTime = 0;
            Int32.TryParse(_config.IOCtrAStart.Value, out ctrIOStartTime);
            m_nud_Io_start.Value = ctrIOStartTime;

            int ctrIOSpanTime = 0;
            Int32.TryParse(_config.IOCtrASpan.Value, out ctrIOSpanTime);
            m_nud_io_span.Value = ctrIOSpanTime;

            m_tbx_bin1_code.Text = _config.CodeToBin.GetItemValue(0);
            m_tbx_bin2_code.Text = _config.CodeToBin.GetItemValue(1);
            m_tbx_bin3_code.Text = _config.CodeToBin.GetItemValue(2);
            m_tbx_bin4_code.Text = _config.CodeToBin.GetItemValue(3);
            switch (_config.DefaultBin.Value)
            {
                case "1":
                    m_rbt_bin1_default.Checked = true;
                    break;
                case "2":
                    m_rbt_bin2_default.Checked = true;
                    break;
                case "3":
                    m_rbt_bin3_default.Checked = true;
                    break;
                case "4":
                    m_rbt_bin4_default.Checked = true;
                    break;
                default:
                    m_rbt_bin4_default.Checked = true;
                    break;

            }
            m_rbt_bin1_default.Checked = false;
            // test board abnormal code
            m_tbx_test_abnormal_code.Text = _config.TestboardEvCode.Value;

            // temperature 
            if (_config.HightTempSupport.Value == "1")
            {
                m_nud_hight_temperature.Value = decimal.Parse(_config.HightTempValue.Value);
            }
            else
            {
                m_nud_hight_temperature.Enabled = false;
            }

            if (_config.UseDiffReparation.CheckBoolValue())
            {
                m_cbx_diff_reparation.Checked = true;
                m_btn_diff_reparation_setting.Visible = true;
            }
            //if(_config.TempControlEnable.Value == "1")
            //{
            //    m_cbx_tempCtr_enable.Checked = true;
            //}else
            //{
            //    m_cbx_tempCtr_enable.Checked = false;
            //}
            decimal tempMistake = 0;
            decimal.TryParse(_config.TempMistake.Value, out tempMistake);
            m_nud_temp_mistake.Value = tempMistake;

            decimal tempReparation = 0;
            decimal.TryParse(_config.TempReparation.Value, out tempReparation);
            m_nud_temp_reparation.Value = tempReparation;

            if (_config.LowTempSupport.Value == "1")
            {
                m_nud_low_temperature.Value = int.Parse(_config.LowTempValue.Value);
            }
            else
            {
                m_nud_low_temperature.Enabled = false;
            }



            if (_config.DebugBoardTest.Value == "1")
            {
                m_cbx_checkBoard_mode.Checked = true;
            }
            else
            {
                m_cbx_checkBoard_mode.Checked = false;
            }
            

            if (_config.DiagnosticMode.Value == "1")
            {
                m_cbx_diagnostic_mode.Checked = true;
            }
            else
            {
                m_cbx_diagnostic_mode.Checked = false;
            }
            if (_config.TempCtrInitAllEnable.CheckBoolValue())
            {
                m_cbx_temp_enable_all.Checked = true;
            }
            else
            {
                m_cbx_temp_enable_all.Checked = false;
            }

            if (_config.IdlePowerHold.CheckBoolValue())
            {
                m_cbx_idle_power_on.Checked = true;
            }
            else
            {
                m_cbx_idle_power_on.Checked = false;
            }

            m_cbx_orderBy_stage.Checked = _config.OrderBinByStage.CheckBoolValue();

            if (!_debugMode)
            {
                m_cbx_checkBoard_mode.Enabled = false;
                m_cbx_diagnostic_mode.Enabled = false;
                m_cbx_temp_enable_all.Enabled = false;
                m_cbx_idle_power_on.Enabled = false;
                m_gbx_function.Enabled = false;
                m_btn_policy_choise.Enabled = false;
            }

            UpdateParameterEnable();
        }

        private void UpdateParameterEnable()
        {

            m_cbx_selected_io.Enabled = _bAdminRole;
            m_nud_Io_start.Enabled = _bAdminRole;
            m_nud_io_span.Enabled = _bAdminRole;
            m_nud_control_batch.Enabled = _bAdminRole;
            m_btn_csv_setting.Enabled = _bAdminRole;
            m_gbx_bin_code.Enabled = _bAdminRole;
            m_tbx_test_abnormal_code.Enabled = _bAdminRole;
            m_txt_dest_ip.Enabled = _bAdminRole;
            m_nud_dest_port.Enabled = _bAdminRole;
            m_pal_ip_list.Enabled = _bAdminRole;
            m_gbx_temperature.Enabled = _bAdminRole;
            m_gbx_function.Enabled = _bAdminRole;

        }

        private bool BinCodeCheck(string binCode)
        {
            if (binCode == null || binCode.Length == 0)
            {
                return true;
            }
            string[] codeArray = binCode.Split(',');
            IFormatProvider provider = CultureInfo.InvariantCulture;
            int result = 0;
            foreach (var v in codeArray)
            {
                if (!Int32.TryParse(v, NumberStyles.HexNumber, provider, out result))
                {
                    return false;
                }
                else if (result < byte.MinValue || result > byte.MaxValue)
                {
                    return false;
                }
            }

            return true;
        }

        private void OnBtnOKClick(object sender, EventArgs e)
        {
            bool addrCheck = true;
            bool reboot = false;
            string[] newIPs = new string[SysConfig.DEV_NUM * SysConfig.TEAM_GROUP_NUM];
            if (!_debugMode)
            {
                Password pwdCheckDlg = new Password("10086");
                pwdCheckDlg.Text = "请输入修改密码";
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
            }
            for (int i = 1; i <= SysConfig.DEV_NUM * SysConfig.TEAM_GROUP_NUM; i++)
            {
                string ipStr = m_pal_ip_list.Controls["txt" + i].Text;
                IPAddress ip;
                if (!IPAddress.TryParse(ipStr, out ip))
                {
                    addrCheck = false;
                    break;
                }
                else
                {
                    newIPs[i - 1] = ipStr;
                }
            }
            if (!addrCheck)
            {
                MessageBox.Show("板卡地址不合法，有无效的IP地址");
                return;
            }
            for (int i = 0; i < SysConfig.DEV_NUM * SysConfig.TEAM_GROUP_NUM; i++)
            {
                for (int j = 0; j < SysConfig.DEV_NUM * SysConfig.TEAM_GROUP_NUM; j++)
                {
                    if (i != j && newIPs[i] == newIPs[j])
                    {
                        MessageBox.Show("IP地址有重复");
                        return;
                    }
                }
            }
            // 检查Bin code
            if (!BinCodeCheck(m_tbx_bin1_code.Text)
                || !BinCodeCheck(m_tbx_bin2_code.Text)
                || !BinCodeCheck(m_tbx_bin3_code.Text)
                || !BinCodeCheck(m_tbx_bin4_code.Text))
            {
                MessageBox.Show("分Bin 状态码格式错误，请按照XX,XX格式（采用十六进制编码),为空代表不使用");
                return;
            }

            // 检查测试异常码
            if (!BinCodeCheck(m_tbx_test_abnormal_code.Text))
            {
                MessageBox.Show("测试异常码格式错误，请按照XX,XX格式（采用十六进制编码),为空代表不使用");
                return;
            }
            if (m_txt_dest_ip.Text != _config.DestIp.Value)
            {
                IPAddress ip;
                if (!IPAddress.TryParse(m_txt_dest_ip.Text, out ip))
                {
                    MessageBox.Show("机台地址不合法");
                    return;
                }
                _config.DestIp.Value = m_txt_dest_ip.Text;
            }

            if (m_cbx_selected_io.SelectedIndex != _firstIOSelectIndex)
            {
                int groupId = m_cbx_selected_io.SelectedIndex;
                if (groupId <= 0 || groupId >= (int)EIOGroup.SWITCH_GROUP_NUM)
                {
                    _config.IOCtrAId.Value = ((UInt16)(EIOGroup.SWITCH_GROUP_INVALID)).ToString();
                }
                else
                {
                    _config.IOCtrAId.Value = groupId.ToString();
                }
            }
            if (m_nud_Io_start.Value != Int32.Parse(_config.IOCtrAStart.Value))
            {
                _config.IOCtrAStart.Value = m_nud_Io_start.Value.ToString();
            }
            if (m_nud_io_span.Value != Int32.Parse(_config.IOCtrASpan.Value))
            {
                _config.IOCtrASpan.Value = m_nud_io_span.Value.ToString();
            }
            if (m_nud_control_batch.Value != Int32.Parse(_config.IOCtrBatch.Value))
            {
                _config.IOCtrBatch.Value = m_nud_control_batch.Value.ToString();
            }

            if (m_nud_dest_port.Value != Int32.Parse(_config.DestPort.Value))
            {
                _config.DestPort.Value = m_nud_dest_port.Value.ToString();
            }
            //
            if (m_txt_config_path.Text != null)
            {
                if (m_txt_config_path.Text != _config.TestPolicyPath)
                {
                    if (_debugMode)
                    {
                        string errorMsg = "";
                        PolicyFile obj = PolicyFile.Deserialize(SysConfig.GetPolicyFileFullPath(m_txt_config_path.Text), ref errorMsg);
                        if (obj == null)
                        {
                            MessageBox.Show("读取配置文件失败");
                            return;
                        }
                        _config.DebugPolicyConfig.Value = m_txt_config_path.Text;
                    }
                }
            }

            for (int i = 0; i < newIPs.Count(); i++)
            {
                if (i < SysConfig.DEV_NUM)
                {
                    _config.GroupAIp.SetItem(i, newIPs[i]);
                }
                else
                {
                    _config.GroupBIp.SetItem(i % SysConfig.DEV_NUM, newIPs[i]);
                }

            }

            _config.CodeToBin.SetItem(0, m_tbx_bin1_code.Text);
            _config.CodeToBin.SetItem(1, m_tbx_bin2_code.Text);
            _config.CodeToBin.SetItem(2, m_tbx_bin3_code.Text);
            _config.CodeToBin.SetItem(3, m_tbx_bin4_code.Text);

            if (m_rbt_bin1_default.Checked)
            {
                _config.DefaultBin.Value = "1";
            }
            else if (m_rbt_bin2_default.Checked)
            {
                _config.DefaultBin.Value = "2";
            }
            else if (m_rbt_bin3_default.Checked)
            {
                _config.DefaultBin.Value = "3";
            }
            else
            {
                _config.DefaultBin.Value = "4";
            }
            // test board abnormal code
            if (_config.TestboardEvCode.Value != m_tbx_test_abnormal_code.Text)
            {
                _config.TestboardEvCode.Value = m_tbx_test_abnormal_code.Text;
            }

            // temp
            if (_config.HightTempSupport.Value == "1")
            {
                if (_config.HightTempValue.Value != m_nud_hight_temperature.Value.ToString())
                {
                    _config.HightTempValue.Value = m_nud_hight_temperature.Value.ToString();
                }
            }


            if (_config.LowTempSupport.Value == "1")
            {
                if (m_nud_low_temperature.Value != int.Parse(_config.LowTempValue.Value))
                {
                    _config.LowTempValue.Value = m_nud_low_temperature.Value.ToString();
                }
            }
            if (_config.DebugBoardTest.Value == "1")
            {
                if (!m_cbx_checkBoard_mode.Checked)
                {
                    _config.DebugBoardTest.Value = "0";
                }
            }
            else
            {
                if (m_cbx_checkBoard_mode.Checked)
                {
                    _config.DebugBoardTest.Value = "1";
                }
            }

            if (!_debugMode)
            {
                m_cbx_diagnostic_mode.Checked = false;
            }

            if (m_cbx_diagnostic_mode.Checked)
            {
                if (_config.DiagnosticMode.Value != "1")
                {
                    _config.DiagnosticMode.Value = "1";
                }
            }
            else if (_config.DiagnosticMode.Value != "0")
            {
                _config.DiagnosticMode.Value = "0";
            }

            if (m_cbx_temp_enable_all.Checked)
            {
                if (_config.TempCtrInitAllEnable.Value != "1")
                {
                    _config.TempCtrInitAllEnable.Value = "1";
                }
            }
            else if (_config.TempCtrInitAllEnable.Value != "0")
            {
                _config.TempCtrInitAllEnable.Value = "0";
            }

            if (m_cbx_idle_power_on.Checked)
            {
                if (_config.IdlePowerHold.Value != "1")
                {
                    _config.IdlePowerHold.Value = "1";
                }
            }
            else if (_config.IdlePowerHold.Value != "0")
            {
                _config.IdlePowerHold.Value = "0";
            }

            if (m_cbx_diff_reparation.Checked)
            {
                if (!_config.UseDiffReparation.CheckBoolValue())
                {
                    _config.UseDiffReparation.SetTrue();
                }
            }
            else
            {
                if (_config.UseDiffReparation.CheckBoolValue())
                {
                    _config.UseDiffReparation.SetFalse();
                }
            }

            if(m_cbx_orderBy_stage.Checked != _config.OrderBinByStage.CheckBoolValue())
            {
                if(m_cbx_orderBy_stage.Checked)
                {
                    _config.OrderBinByStage.SetTrue();
                }
                else
                {
                    _config.OrderBinByStage.SetFalse();
                }
            }
            //if (m_cbx_tempCtr_enable.Checked)
            //{
            //    if(_config.TempControlEnable.Value != "1")
            //    {
            //        _config.TempControlEnable.Value = "1";
            //    }
            //}
            //else
            //{
            //    if (_config.TempControlEnable.Value != "0")
            //    {
            //        _config.TempControlEnable.Value = "0";
            //    }
            //}

            //Int32 tempMistake = 0;
            //Int32.TryParse(_config.TempMistake.Value, out tempMistake);
            _config.TempMistake.Value = m_nud_temp_mistake.Value.ToString();

            _config.TempReparation.Value = m_nud_temp_reparation.Value.ToString();

            //if (m_rbt_groupA.Checked)
            //{
            //    if (_config.GroupSelect.Value != "0")
            //    {
            //        _config.GroupSelect.Value = "0";
            //        reboot = true;
            //    }
            //}
            //else
            //{
            //    if (_config.GroupSelect.Value != "1")
            //    {
            //        _config.GroupSelect.Value = "1";
            //        reboot = true;
            //    }
            //}
            //if (m_rbt_order01.Checked)
            //{
            //    if (Int32.Parse(_config.DutOrder.Value) != SysConfig.DUT_ORDER_LEFT_TO_RIGHT)
            //    {
            //        _config.DutOrder.Value = SysConfig.DUT_ORDER_LEFT_TO_RIGHT.ToString();
            //        reboot = true;
            //    }
            //}
            //else
            //{
            //    if (Int32.Parse(_config.DutOrder.Value) != SysConfig.DUT_ORDER_RIGHT_TO_LEFT)
            //    {
            //        _config.DutOrder.Value = SysConfig.DUT_ORDER_RIGHT_TO_LEFT.ToString();
            //        reboot = true;
            //    }
            //}
            //if (_config.BoardProtocol.Value != m_cbx_board_protocol.Text)
            //{
            //    _config.BoardProtocol.Value = m_cbx_board_protocol.Text;
            //    reboot = true;
            //}

            //m_cbx_board_protocol.SelectAll();

            _config.ChangeConfigEnd();

            this.DialogResult = DialogResult.OK;
            _rebootFlag = reboot;
            Close();
        }

        private void OnBtnCancelClick(object sender, EventArgs e)
        {
            this.DialogResult = DialogResult.Cancel;
            this.Close();
        }

        private void OnSelectIOChange(object sender, EventArgs e)
        {

        }

        private void OnEditGroupBtnClick(object sender, EventArgs e)
        {

        }

        private bool SendMessageToHiddenWindow(string processName, int message, int wparam, int lparam)
        {
            IntPtr windowHandle = FindWindow(null, processName);

            if (windowHandle != IntPtr.Zero)
            {
                SendMessage(windowHandle, message, wparam, lparam);
                IntPtr hWndTopMost = new IntPtr(-1);
                SetWindowPos(windowHandle, hWndTopMost, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
                return true;
            }


            return false;
        }

        public static async Task<bool> SendMessageToLauchWindow(string processName, int message, int wparam, int lparam)
        {
            //IntPtr windowHandle = FindWindow(null, processName);
            IntPtr windowHandle = IntPtr.Zero;
            Process process = new Process();
            process.StartInfo.Arguments = "show";
            process.StartInfo.FileName = processName;
            try
            {
                if (process.Start())
                {
                    //Thread.Sleep(200);
                    await Task.Delay(200);
                    if (processName.EndsWith(".exe"))
                    {
                        windowHandle = FindWindow(null, processName.Substring(0, processName.Length - 4));
                    }
                    else
                    {
                        windowHandle = FindWindow(null, processName);
                    }
                }
            }
            catch (Exception ex)
            {
                Hlog.E(ex.Message);
                return false;
            }


            if (windowHandle != IntPtr.Zero)
            {
                SendMessage(windowHandle, message, wparam, lparam);
                return true;
            }
            return false;
        }
        private async void OnBtnLogSettingClick(object sender, EventArgs e)
        {
            const int WM_USER = 0x0400;
            const int WM_ICON_NOTIFY = WM_USER + 100;
            const int WM_LBUTTONDOWN = 0x0201;
            if (SendMessageToHiddenWindow("LogPrintTool", WM_ICON_NOTIFY, 0, WM_LBUTTONDOWN) == false)
            {
                if (MessageBox.Show("log 打印程序未启动,是否尝试启动？", "log 设置", MessageBoxButtons.OKCancel) == DialogResult.OK)
                {
                    bool ret = await SendMessageToLauchWindow("LogPrintTool.exe", WM_ICON_NOTIFY, 0, WM_LBUTTONDOWN);
                    if (ret == false)
                    {
                        MessageBox.Show("程序启动失败，请检查程序目录是否有 LogPrintTool.exe");
                    }
                }
            }
        }

        private void OnBtnCSVSettingClick(object sender, EventArgs e)
        {
            CSVSetting csvSetting = new CSVSetting();
            csvSetting.Show();
        }

        private void OnBtnAuthClick(object sender, EventArgs e)
        {
            Password pwdCheckDlg = new Password("cc9988");
            pwdCheckDlg.Text = "请输入管理员密码";
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

            _bAdminRole = true;
            UpdateParameterEnable();
        }

        private void OnDutsStateCheck(object sender, EventArgs e)
        {
            EMMDlg dlg = new EMMDlg();
            dlg.ShowDialog();
        }

        private void m_btn_m_cbx_diff_reparation_Click(object sender, EventArgs e)
        {
            TempReparation dlg = new TempReparation(_bsControl);
            dlg.ShowDialog();
        }

        private void m_cbx_diff_reparation_CheckedChanged(object sender, EventArgs e)
        {
            if (m_cbx_diff_reparation.Checked)
            {
                m_btn_diff_reparation_setting.Visible = true;
            }
            else
            {
                m_btn_diff_reparation_setting.Visible = false;
            }
        }

        private void m_cbx_diagnostic_mode_CheckedChanged(object sender, EventArgs e)
        {

        }

        private void OnSelectPolicyClick(object sender, EventArgs e)
        {
            string policyFolderPath = Path.Combine(Application.StartupPath, SysConfig.PolicyFolderPath);
            OpenFileDialog ofile = new OpenFileDialog();
            ofile.Title = "选择配置文件";
            ofile.InitialDirectory = policyFolderPath;
            ofile.Filter = SysConfig.PolicyFileFilter;
            ofile.RestoreDirectory = true;
            if (ofile.ShowDialog() == DialogResult.OK)
            {
                if (ofile.FileName.Contains(policyFolderPath + "\\"))
                {
                    string relativePath = Tools.GetRelativePath(policyFolderPath, ofile.FileName);
                    string extName = Path.GetExtension(ofile.FileName);
                    m_txt_config_path.Text = relativePath.Substring(0, relativePath.Length - extName.Length);
                }
                else
                {
                    MessageBox.Show("不支持默认文件夹以外路径的文件");
                }
            }
        }

        private void m_txt_config_path_TextChanged(object sender, EventArgs e)
        {

        }
    }
}
