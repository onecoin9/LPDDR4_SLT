using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using Hsg.Common;
using Hsg.BLL.Model;

namespace Hsg.View
{

    public partial class TestTeam : UserControl
    {
        private int _teamId = 0;
        private BindingSource bindingSource = new BindingSource();
        private TestTeamlView _viewModel;
        private BSController _bsControl;
        private Timer TestTimer = new Timer(); // 模拟多次测试
        //private TestTeamlView ViewModel { get { return _viewModel; } }
        public TestTeam(BSController bsControl, TestTeamlView viewModel, int teamId)
        {
            InitializeComponent();
            _teamId = teamId + 1;
            _viewModel = viewModel;
            _bsControl = bsControl;
            m_lb_boardId.Text = (teamId + 1).ToString("D2");
            bindingSource.DataSource = viewModel;
            m_txt_description.DataBindings.Add("Text", bindingSource, "StateDescript");
            m_txt_description.DataBindings.Add("ForeColor", bindingSource, "StateColor");

            m_txt_test_time.DataBindings.Add("Text", bindingSource, "TimeCount");
            int group1Count = flowLayoutPanel1.Controls.Count;
            for (int i = 1; i <= group1Count; i++)
            {
                int id = i + (i - 1) / 4 * 4;
                Button btn = flowLayoutPanel1.Controls["button" + id] as Button;
                //  Console.WriteLine("Bind " + btn.Text);
                if (btn != null)
                {
                    // btn.DataBindings.Add("ForeColor", bindingSource, "Dut" + (i + 1).ToString() + "Color");
                    btn.DataBindings.Add("BackColor", bindingSource, "Dut" + id.ToString() + "Color");
                    if (_bsControl.TempControlIsOpen())
                    {
                        btn.DataBindings.Add("Text", bindingSource, "TempValue" + id.ToString());
                    }
                    else
                    {
                        btn.Text = "";
                    }
                    btn.Click += OnDutStateClick;
                }
            }

            //  Console.WriteLine("Bind B");
            int group2Count = flowLayoutPanel2.Controls.Count;
            for (int i = 1; i <= group2Count; i++)
            {
                int id = i + (i - 1 + 4) / 4 * 4;
                Button btn = flowLayoutPanel2.Controls["button" + id] as Button;
                //  Console.WriteLine("Bind " + btn.Text);
                if (btn != null)
                {
                    // btn.DataBindings.Add("ForeColor", bindingSource, "Dut" + (i + 1).ToString() + "Color");
                    btn.DataBindings.Add("BackColor", bindingSource, "Dut" + id.ToString() + "Color");
                    if (_bsControl.TempControlIsOpen())
                    {
                        btn.DataBindings.Add("Text", bindingSource, "TempValue" + id.ToString());
                    }
                    else
                    {
                        btn.Text = "";
                    }
                    btn.Click += OnDutStateClick;
                }
            }
            buttonA.DataBindings.Add("BackColor", bindingSource, "BoardAColor");
            buttonB.DataBindings.Add("BackColor", bindingSource, "BoardBColor");
            m_lb_boardId.DataBindings.Add("BackColor", bindingSource, "TeamAbnormalColor");
        }

        private void TestTeam_Load(object sender, EventArgs e)
        {

        }
        protected override void OnHandleCreated(EventArgs e)
        {
            // base.OnHandleCreated(e);
            //   this.SetStyle(ControlStyles.OptimizedDoubleBuffer | ControlStyles.AllPaintingInWmPaint, true);
        }

        private void SetDialogPositon(Form dlg)
        {
            Point pt;
            if (_teamId > 10)
            {
                pt = new Point(Control.MousePosition.X, Control.MousePosition.Y);
            }
            else
            {
                pt = new Point(Control.MousePosition.X - dlg.Width, Control.MousePosition.Y);
            }
            dlg.Location = pt;
        }
        private void m_txt_description_Click(object sender, EventArgs e)
        {
            if (_viewModel.Stage == TestStage.ST_TESTING)
            {
                ChoiseDlg dlg = new ChoiseDlg("选择", "是否取消当前测试？");
                SetDialogPositon(dlg);
                if (dlg.ShowDialog() == DialogResult.OK)
                {
                    _bsControl.OnCancelTest(_teamId - 1);
                    return;
                }
                return;
            }


            if (_bsControl.IsDebugMode() && !_bsControl.IsStartService())
            {
                string errorMsg = "";
                if (!_bsControl.CheckWorkEnvironment(ref errorMsg))
                {
                    MessageBox.Show(errorMsg);
                    return;
                }
                if (_viewModel.Stage == TestStage.ST_READY || _viewModel.Stage > TestStage.ST_TESTING)
                {
                    ChoiseDlg dlg = new ChoiseDlg("选择", "是否启动测试当前板卡？");
                    SetDialogPositon(dlg);
                    if (dlg.ShowDialog() == DialogResult.OK)
                    {
                        _bsControl.OnImitateTest(_teamId - 1);
                        // 用于调试
                        //TestTimer.Stop(); 
                        //TestTimer.Tick += OnWorkTimerTick;
                        //TestTimer.Interval = 180000;
                        //TestTimer.Start();
                        return;
                    }
                    return;
                }
            }

            
            
        }

        void FormClosingEventHandler(object sender, FormClosingEventArgs e)
        {
            _viewModel.ViewEnable = false;
        }

        private void OnWorkTimerTick(object sender, EventArgs e)
        {
            _bsControl.OnImitateTest(_teamId - 1);
        }

        private void On_BoardA_Click(object sender, EventArgs e)
        {
            if (_viewModel.GroupDetail[0]?.Length > 0)
            {
                InforDialog inforDlg;
                string title = string.Format(@"板卡A");
                inforDlg = new InforDialog(title, _viewModel.GroupDetail[0]);
                inforDlg.TopLevel = true;
                SetDialogPositon(inforDlg);
                inforDlg.ShowDialog();
            }
        }

        private void On_BoardB_Click(object sender, EventArgs e)
        {
            if (_viewModel.GroupDetail[1]?.Length > 0)
            {
                InforDialog inforDlg;
                string title = string.Format(@"板卡B");
                inforDlg = new InforDialog(title, _viewModel.GroupDetail[1]);
                inforDlg.TopLevel = true;
                SetDialogPositon(inforDlg);
                inforDlg.ShowDialog();
            }
        }

        private void OnTeamAlarmClick(object sender, EventArgs e)
        {
            if (_viewModel.AlarmFlag)
            {
                _bsControl.OnPauseAlarmCountdown(_teamId - 1);
                AlarmDlg alarm = new AlarmDlg(_bsControl, _viewModel, _teamId);
                alarm.ShowDialog();
                _bsControl.OnResumeAlarmCountdown(_teamId - 1);
                //DialogResult ret = MessageBox.Show(_viewModel.AlarmMsg + ",是否重测", "警告处理", MessageBoxButtons.OKCancel);
                //if (ret == DialogResult.OK) // 手动重测
                //{
                //    _bsControl.OnRetryAbnormalTest(_teamId - 1);
                //}
            }
            else
            {
                if(_viewModel.Stage >= TestStage.ST_READY)
                {
                    if(MessageBox.Show($"请确定, 分选机已经关闭当前测试组{_teamId}","刷新测试组状态", MessageBoxButtons.YesNo) == DialogResult.Yes)
                    {
                        Password pwd = new Password("10086");
                        if(pwd.ShowDialog()== DialogResult.OK)
                        {
                            _bsControl.RefreshEnverionment(_teamId - 1);
                        }
                    }
                } else
                {
                    _bsControl.RefreshEnverionment(_teamId - 1);
                }
                
            }
        }

        private void OnTimeClick(object sender, EventArgs e)
        {
            if (_viewModel.TeamDetail?.Length > 0)
            {
                InforDialog inforDlg;
                string title = string.Format(@"测试组{0}", _teamId);
                string content = "";
                try
                {
                    content = _viewModel.TeamDetail.ToString();
                }catch
                {
                    Console.WriteLine("TeamDetail read assert");
                }
                inforDlg = new InforDialog(title, content);
                inforDlg.TopLevel = true;
                SetDialogPositon(inforDlg);
                inforDlg.ShowDialog();
            }
        }

        private void OnDutStateClick(object sender, EventArgs e)
        {
            Button btn = sender as Button;
            int id = Int32.Parse(btn.Name.Substring(6));
            InforDialog inforDlg;
            if (id >= 0)
            {
                string title = string.Format($"测试板{id}");
                string content = "";
                try
                {
                    content = _viewModel.DutsDetail[id - 1].ToString();
                    if (content.Length == 0)
                    {
                        return;
                    }
                }
                catch
                {
                    Console.WriteLine("DutsDetail read assert");
                }
                inforDlg = new InforDialog(title, content);
                inforDlg.TopLevel = true;
                SetDialogPositon(inforDlg);
                inforDlg.ShowDialog();
            }
        }
    }
}
