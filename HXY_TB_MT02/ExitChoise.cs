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
    public partial class ExitChoise : Form
    {
        public ExitChoise()
        {
            InitializeComponent();
        }

        private void m_btn_quit_Click(object sender, EventArgs e)
        {
            DialogResult = DialogResult.No;
            Close();
        }

        private void m_btn_close_workOrder_Click(object sender, EventArgs e)
        {
            Password pwd = new Password("10086");
            if(pwd.ShowDialog() == DialogResult.OK)
            {
                DialogResult = DialogResult.Yes;
                Close();
            } else
            {
                MessageBox.Show("授权密码错误");
            }
           
        }

        private void m_btn_back_Click(object sender, EventArgs e)
        {
            DialogResult = DialogResult.Cancel;
            Close();
        }
    }
}
