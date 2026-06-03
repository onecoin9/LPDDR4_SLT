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
    public partial class ChoiseDlg : Form
    {
        private string _titile;
        private string _content;
        public ChoiseDlg(string  title, string content)
        {
            InitializeComponent();
            _titile = title;
            _content = content;
        }

        private void ChoiseDlg_Load(object sender, EventArgs e)
        {
            this.Text = _titile;
            m_txt_content.Text = _content;
        }

        private void OnOkClick(object sender, EventArgs e)
        {
            this.DialogResult = DialogResult.OK;
        }

        private void OnClickCancel(object sender, EventArgs e)
        {
            this.DialogResult = DialogResult.Cancel;
        }
    }
}
