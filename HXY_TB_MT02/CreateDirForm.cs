using Hsg.BLL;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Hsg.View
{
    public partial class CreateDirForm : Form
    {
        public CreateDirForm()
        {
            InitializeComponent();
        }
        public string NewSubDir = "";

        private void btn_ok_Click(object sender, EventArgs e)
        {
            if(txt_dir_name.Text.Length > 0)
            {
                string path = Path.Combine(Application.StartupPath, SysConfig.PolicyFolderPath, txt_dir_name.Text);
                try
                {
                    Directory.CreateDirectory(path);
                    DialogResult = DialogResult.OK;
                    NewSubDir = txt_dir_name.Text;
                    Close();
                }
                catch(Exception ex)
                {
                    MessageBox.Show(ex.Message);
                }
            }
        }

        private void btn_cancel_Click(object sender, EventArgs e)
        {
            Close();
        }
    }
}
