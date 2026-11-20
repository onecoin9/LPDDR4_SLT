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
    public partial class InforDialog : Form
    {
        private string _title;
        private string _content;
        private Func<string> _contentProvider;
        private bool _close = false;
        private int _line = 0;
        private Timer _refreshTimer;
        public InforDialog(string title, string [] content)
        {
            _title = title;
            _content = "";
            _line = content.GetLength(0);
            for (int i = 0; i < content.GetLength(0); i++)
            {
                if (i > 0)
                {
                    _content += "\r\n";
                }
                _content += ">";
                _content += _content[i];
            }
            InitializeComponent();
            foreach(var v in this.Controls)
            {
                ((Control)v).Click += OnFrameClick;
            }
        }
        public InforDialog(string title, string content)
        {
            _title = title;
            _content = content;
            _line = _content.Split('\r').Length;
            InitializeComponent();
            foreach (var v in this.Controls)
            {
                ((Control)v).Click += OnFrameClick;
            }
        }

        public InforDialog(string title, Func<string> contentProvider)
        {
            _title = title;
            _contentProvider = contentProvider;
            _content = _contentProvider?.Invoke() ?? "";
            _line = _content.Split('\r').Length;
            InitializeComponent();
        }

        private void InforDialog_Load(object sender, EventArgs e)
        {

            this.Text = _title;
            SetContent(_content);
            int calcHeight = Font.Height * (_line + 3) + 20;
            this.Height = calcHeight > 400 ? 400 : calcHeight;

            if (_contentProvider != null)
            {
                _refreshTimer = new Timer();
                _refreshTimer.Interval = 300;
                _refreshTimer.Tick += OnRefreshTimerTick;
                _refreshTimer.Start();
            }
        }

        private void OnRefreshTimerTick(object sender, EventArgs e)
        {
            string latest = _contentProvider?.Invoke() ?? "";
            if (latest == _content)
            {
                return;
            }

            _content = latest;
            SetContent(latest);
        }

        private void SetContent(string content)
        {
            bool scrollToEnd = m_rbx_content.SelectionStart >= m_rbx_content.TextLength - 2;
            m_rbx_content.Text = content;
            if (scrollToEnd)
            {
                m_rbx_content.SelectionStart = m_rbx_content.TextLength;
                m_rbx_content.ScrollToCaret();
            }
        }

        private void OnFrameClick(object sender, EventArgs e)
        {
            if (_contentProvider != null && sender == m_rbx_content)
            {
                return;
            }

            if (!_close)
            {
                _close = true;
                Close();
            }
        }

        private void InforDialog_Deactivate(object sender, EventArgs e)
        {

        }

        protected override void OnFormClosed(FormClosedEventArgs e)
        {
            _refreshTimer?.Stop();
            _refreshTimer?.Dispose();
            _refreshTimer = null;
            base.OnFormClosed(e);
        }
    }
}
