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
        private bool _close = false;
        private int _line = 0;
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

        private void InforDialog_Load(object sender, EventArgs e)
        {
            
            this.Text = _title;
            m_rbx_content.Text = _content;
            this.Height = Font.Height *(_line + 3) + 20;
        }


        private void OnFrameClick(object sender, EventArgs e)
        {
            if (!_close)
            {
                _close = true;
                Close();
            }
        }

        private void InforDialog_Deactivate(object sender, EventArgs e)
        {

        }
    }
}
