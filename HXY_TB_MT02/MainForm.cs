using Hsg.BLL;
using Hsg.BLL.Model;
using Hsg.Common;
using Hsg.Common.ADO;
using System;
using System.Collections.Concurrent;
using System.Drawing;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
namespace Hsg.View
{
    public partial class MainForm : Form
    {
        private BindingSource bindingSource = new BindingSource();
        private BSMainViewModel viewModel;
        private BSController _bsControl;
        private HsgLogger _logger;
        public bool Is_DebugMode { get; set; }
        private TestTeamlView[] _testTeamlView;
        private int _loadColumn = 0;
        private bool _winClosing = false;
        private ConcurrentQueue<Tuple<string, Color>> logQueue = new ConcurrentQueue<Tuple<string, Color>>();
        private readonly SynchronizationContext _synchronizationContext = SynchronizationContext.Current; // 假设这是在 UI 线程上初始化的
        //  private List<TestTeam> _teamList;
        public MainForm()
        {
            SysConfig config = SysConfig.GetInstance();
            InitializeComponent();
            viewModel = new BSMainViewModel();
            bindingSource.DataSource = viewModel;
            m_txt_work_time.DataBindings.Add("Text", bindingSource, nameof(viewModel.WorkTime));
            //m_txt_order_no.DataBindings.Add("Text", bindingSource, nameof(viewModel.OrderNumber));
            //m_txt_material_no.DataBindings.Add("Text", bindingSource, nameof(viewModel.MaterialNumber));
            m_txt_test_workOrder.Text = SysConfig.WorkOrderNo;
            m_txt_test_tatistics.DataBindings.Add("Text", bindingSource, nameof(viewModel.TestStatistics));
            m_txt_conn_state.DataBindings.Add("Text", bindingSource, nameof(viewModel.HanderServerState));
            m_txt_service_state.DataBindings.Add("Text", bindingSource, nameof(viewModel.ServiceState));
            m_txt_online_team.DataBindings.Add("Text", bindingSource, nameof(viewModel.OnlineBoardStatistics));
            m_txt_emi_path.DataBindings.Add("Text", bindingSource, nameof(viewModel.PolicyName));
            m_txt_work_mode.DataBindings.Add("Text", bindingSource, nameof(viewModel.WorkMode));

            m_btn_start.DataBindings.Add("Enabled", bindingSource, nameof(viewModel.ServiceEnableStart));
            m_btn_pause.DataBindings.Add("Enabled", bindingSource, nameof(viewModel.ServiceEnablePause));

            m_txt_order_no.Text = SysConfig.OrderNo;
            m_txt_material_no.Text = SysConfig.MaterialNo;
            m_txt_workStage.Text = SysConfig.WorkStageDescription;
            Hlog.UserDebugSaveFile();
            int logLevel = -1;
            Int32.TryParse(config.LogLevel.Value, out logLevel);
            Hlog.SetLogLevel(logLevel);
            _logger = new HsgLogger();
            string version = typeof(MainForm).Assembly.GetName().Version.ToString();
            Hlog.I("Version:" + Application.ProductName + "-" + version);
            this.FormClosing += FormClosingEventHandler;
            _testTeamlView = new TestTeamlView[SysConfig.DEV_NUM];
            for (int i = 0; i < SysConfig.DEV_NUM; i++)
            {
                _testTeamlView[i] = new TestTeamlView();
            }
            _bsControl = new BSController(_logger, viewModel, _testTeamlView);
            //_bsControl.SetDebugMode(_isDebugMode);
            _bsControl.BindUIUpdate(AppendLog);
            m_pnl_statusList.Size = new Size(1264, 800);
        }

        private void MainForm_Load(object sender, EventArgs e)
        {
            m_bgw_ui_update.RunWorkerAsync();
            //   m_richbox_update_timer.Start();

        }
        public void ReqCloseWindow()
        {
            this.BeginInvoke((MethodInvoker)(() => Close()));
        }

        private void LoadUiContent(int column)
        {
            int left_gap = 25;
            int top_gap = 20;
            int x_gap = 15;
            int y_gap = 15;
            int i = 0;
            for (i = _loadColumn; i < _loadColumn + column; i++)
            {
                for (int j = 0; j < 10; j++)
                {
                    int id = 50 - (i * 10 + j + 1);
                    TestTeam control = new TestTeam(_bsControl, _testTeamlView[id], id);
                    control.Location = new Point(i * (control.Width + x_gap) + left_gap, j * (control.Height + y_gap) + top_gap);
                    m_pnl_statusList.Controls.Add(control);
                }
            }
            _loadColumn = i;
        }
        private void m_btn_exit_Click(object sender, EventArgs e)
        {
            if (_bsControl.IsWorking())
            {
                MessageBox.Show("当前有未完成的测任务，请等待任务完成或者取消");
                return;
            }
            if (SysConfig.WorkMode == WorkMode.Debug || SysConfig.WorkMode == WorkMode.Slave)
            {
                //Close();
                // _bsControl.DestoryService();
                if (SysConfig.WorkMode == WorkMode.Debug)
                {
                    DialogResult result = MessageBox.Show("是否确认退出?", "退出确认", MessageBoxButtons.YesNo, MessageBoxIcon.Question);
                    if (result != DialogResult.Yes)
                    {
                        // 如果用户确认退出,则调用基类的 WndProc 方法让窗口关闭  
                        return;
                    }
                }
                Close();
            }
            else
            {
                ExitChoise exitDlg = new ExitChoise();
                DialogResult ret = exitDlg.ShowDialog();//MessageBox.Show("退出时，是否关闭工单？", "退出", MessageBoxButtons.YesNoCancel);
                if (ret == DialogResult.Yes)
                {
                    if (SysConfig.WorkMode == WorkMode.OffLine)
                    {
                        if (!DBHandler.Instance.CloseWorkOrder(SysConfig.WorkOrderId))
                        {
                            MessageBox.Show("关闭工单失败");
                            return;
                        }
                    }
                    Close();
                }
                else if (ret == DialogResult.No)
                {
                    Close();
                }
                else
                {
                    return;
                }
            }
        }
        private void OnDestoryService()
        {
            _winClosing = true;
            _bsControl.DestoryService();
        }
        public void AppendLog(string log, LOG_TYPE logType)
        {
            Color color = Color.Red;
            //if (InvokeRequired || m_rtb_log.InvokeRequired)
            //{
            //    BeginInvoke(new Action<string, LOG_TYPE>(AppendLog), log, logType);
            //    return;
            //}

            switch (logType)
            {
                case LOG_TYPE.INFO:
                    // AppendLogText(log, m_rtb_log.ForeColor);
                    color = m_rtb_log.ForeColor;
                    break;
                case LOG_TYPE.DONE:
                    //AppendLogText(log, Color.Green);
                    color = Color.Green;
                    break;
                case LOG_TYPE.ERROR:
                    //AppendLogText(log, Color.Red);
                    color = Color.Red;
                    break;
                case LOG_TYPE.WARNNING:
                    //AppendLogText(log, Color.Yellow);
                    color = Color.Yellow;
                    break;
            }

            logQueue.Enqueue(Tuple.Create(log, color));
            if (logQueue.Count >= 21)// 只记录最近20条，超出的丢掉
            {
                Tuple<string, Color> logEntry;
                logQueue.TryDequeue(out logEntry);
            }
            // 检查是否需要通过 Invoke 调用
            //if (m_rtb_log.InvokeRequired)
            //{
            //    m_rtb_log.Invoke(new Action(ProcessLogQueue));
            //    return;
            //}

            //ProcessLogQueue();
        }


        //private void AppendLogText(string text, Color color)
        //{
        //    string timeStr = DateTime.Now.ToString(@"[HH:mm:ss]");
        //    if(m_rtb_log.IsDisposed || m_rtb_log.Disposing)
        //    {
        //        return;
        //    }
        //    try
        //    {
        //        m_rtb_log.SuspendLayout();
        //        if (m_rtb_log.TextLength > 0)
        //        {
        //            m_rtb_log.AppendText(Environment.NewLine);
        //        }

        //        m_rtb_log.SelectionStart = m_rtb_log.TextLength;
        //        m_rtb_log.SelectionColor = color;
        //        m_rtb_log.AppendText(timeStr);
        //        m_rtb_log.AppendText(text);
        //        m_rtb_log.SelectionColor = m_rtb_log.ForeColor;
        //        m_rtb_log.ScrollToCaret();
        //        m_rtb_log.ResumeLayout();
        //    }
        //    catch
        //    {

        //    }

        //}
        private void ProcessLogQueue()
        {
            bool addNewLog = true;
            int printLine = 0;
            if (logQueue.Count == 0)
            {
                return;
            }
            m_rtb_log.SuspendLayout();
            try
            {
                Tuple<string, Color> logEntry;
                while (logQueue.TryDequeue(out logEntry) && printLine <= 20)
                {
                    string text = logEntry.Item1;
                    Color color = logEntry.Item2;
                    printLine++;
                    string timeStr = DateTime.Now.ToString(@"[HH:mm:ss] ");
                    if (m_rtb_log.TextLength > 0)
                    {
                        m_rtb_log.AppendText(Environment.NewLine);
                    }
                    m_rtb_log.SelectionStart = m_rtb_log.TextLength;
                    m_rtb_log.SelectionColor = color;
                    m_rtb_log.AppendText(timeStr);
                    m_rtb_log.AppendText(text);
                    m_rtb_log.SelectionColor = m_rtb_log.ForeColor;
                    // m_rtb_log.ScrollToCaret();
                    addNewLog = true;
                }

                // 检查是否超过20行
                if (addNewLog)
                {
                    int currentLineCount = m_rtb_log.GetLineFromCharIndex(m_rtb_log.TextLength) + 1;
                    if (currentLineCount > 20)
                    {
                        // 计算需要保留的起始行号
                        int linesToRemove = currentLineCount - 20;
                        int startLineIndex = linesToRemove;

                        // 获取保留部分的起始字符索引
                        int startCharIndex = m_rtb_log.GetFirstCharIndexFromLine(startLineIndex);

                        // 获取当前RTF内容
                        string fullRtf = m_rtb_log.Rtf;

                        // 使用临时RichTextBox解析RTF内容
                        using (RichTextBox tempRtb = new RichTextBox())
                        {
                            tempRtb.Rtf = fullRtf;

                            // 删除前面的内容（保留格式）
                            tempRtb.Select(0, startCharIndex);
                            tempRtb.SelectedRtf = string.Empty;

                            // 将保留的内容重新设置到原RichTextBox
                            m_rtb_log.Rtf = tempRtb.Rtf;
                            m_rtb_log.SelectionStart = m_rtb_log.TextLength;
                        }
                    }
                }
            }
            finally
            {
                m_rtb_log.ResumeLayout();
                // 确保内容滚动到最底部
                m_rtb_log.ScrollToCaret();
            }
        }

        protected override CreateParams CreateParams
        {
            get
            {
                CreateParams cp = base.CreateParams;
                cp.ExStyle |= 0x02000000;
                return cp;
            }
        }

        private void m_btn_start_Click(object sender, EventArgs e)
        {
            string errorMsg = "";
            if (!_bsControl.CheckWorkEnvironment(ref errorMsg))
            {
                MessageBox.Show(errorMsg);
                return;
            }

            _bsControl.StartService();
        }

        void FormClosingEventHandler(object sender, FormClosingEventArgs e)
        {
            viewModel.ViewEnable = false;
            for (int i = 0; i < _testTeamlView.Length; i++)
            {
                _testTeamlView[i].ViewEnable = false; ;
            }
        }

        private void m_btn_setting_Click(object sender, EventArgs e)
        {
            SettingForm settingForm = new SettingForm(_bsControl);
            settingForm.SetConfigMode(Is_DebugMode);
            if (settingForm.ShowDialog() == DialogResult.OK)
            {
                if (settingForm.RebootFlag)
                {
                    _bsControl.DestoryService();
                    System.Diagnostics.Process.Start(System.Reflection.Assembly.GetExecutingAssembly().Location);
                    Close();
                }
            }
        }

        private void m_btn_pause_Click(object sender, EventArgs e)
        {
            if (_bsControl.IsWorking())
            {
                MessageBox.Show("当前有未完成的测任务，请等待任务完成或者取消");
                return;
            }
            _bsControl.StopService();
        }

        private void pictureBox1_Click(object sender, EventArgs e)
        {
            AboutBox about = new AboutBox();
            about.ShowDialog();
        }

        private async void m_bgw_ui_update_DoWork(object sender, System.ComponentModel.DoWorkEventArgs e)
        {
            for (int i = 0; i < 5; i++)
            {
                var v = this.BeginInvoke(new Action<int>(LoadUiContent), 1);
                this.EndInvoke(v);
                if (_winClosing)
                {
                    return;
                }
                //Thread.Sleep(5);
                await Task.Delay(5);
            }
            if (!_winClosing)
            {
                _bsControl.Run();
            }

        }

        private void MainForm_FormClosing(object sender, FormClosingEventArgs e)
        {
            // _bsControl.DestoryService();
            new ProgressWindow(OnDestoryService, "退出系统").ShowDialog();
        }
        protected override void WndProc(ref Message m)
        {
            // 检查消息类型是否为 WM_CLOSE  
            if (m.Msg == 0x10) // 0x10 是 WM_CLOSE 消息的常量值  
            {
                //if(SysConfig.WorkMode == WorkMode.Slave)
                //{
                //    base.WndProc(ref m);
                //    return;
                //}
                if (_bsControl.IsWorking())
                {
                    MessageBox.Show("当前有未完成的测任务，请等待任务完成或者取消");
                    return;
                }
                //// 例如,显示一个确认对话框询问用户是否要退出  
                //DialogResult result = MessageBox.Show("是否确认退出?", "退出确认", MessageBoxButtons.YesNo, MessageBoxIcon.Question);
                //if (result == DialogResult.Yes)
                //{
                //    // 如果用户确认退出,则调用基类的 WndProc 方法让窗口关闭  
                //    base.WndProc(ref m);
                //}
                //else
                //{
                //    // 如果用户不想退出,则不调用基类的 WndProc 方法,阻止窗口关闭  
                //    return;
                //}
                base.WndProc(ref m);
            }
            else
            {
                // 对于其他类型的消息,调用基类的 WndProc 方法进行常规处理  
                base.WndProc(ref m);
            }
        }

        private void m_rtb_log_TextChanged(object sender, EventArgs e)
        {

        }

        private void m_richbox_update_timer_Tick(object sender, EventArgs e)
        {
            if (!_winClosing)
            {
                ProcessLogQueue();
            }
        }

        private void OnMainFormClick(object sender, EventArgs e)
        {
            WindowState = FormWindowState.Minimized;
        }

        private void m_pnl_statusList_Paint(object sender, PaintEventArgs e)
        {

        }

        private void m_txt_material_no_Click(object sender, EventArgs e)
        {

        }
    }
}
