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
    
    public partial class Password : Form
    {
        private string _checkPassword;
        public Password(string checkPwd)
        {
            _checkPassword = checkPwd;
            InitializeComponent();
        }

        private void OnOkBtnClick(object sender, EventArgs e)
        {
            if (m_txt_password.Text == _checkPassword)
            {
                this.DialogResult = DialogResult.OK;
            } else
            {
                this.DialogResult = DialogResult.Retry;
            }
        }

        private void OnCancelBtnClick(object sender, EventArgs e)
        {
            this.DialogResult = DialogResult.Cancel;
            Close();
        }

        private void Password_Load(object sender, EventArgs e)
        {
        }

        private void OnPwdInputKeyDown(object sender, KeyEventArgs e)
        {
            if(e.KeyCode  == Keys.Enter)
            {
                OnOkBtnClick(sender, e);
            }
        }
    }
}
