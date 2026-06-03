using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using Hsg.BLL;

namespace Hsg.View
{
    public partial class CSVSetting : Form
    {
        private SysConfig _config;
        public CSVSetting()
        {
            _config = SysConfig.GetInstance();
            InitializeComponent();
        }

        private void SCVSetting_Load(object sender, EventArgs e)
        {
            string[] titleList = _config.CSVDetailTitle.Value.Split(',');
            for(int i=0;i<titleList.Length;i++)
            {
                m_lbx_titles.Items.Add(titleList[i]);
            }
            m_txt_csv_path.Text = _config.CSVFilePath.Value;
        }

        private void OnMouseDoubleClick(object sender, MouseEventArgs e)
        {
            int index = m_lbx_titles.IndexFromPoint(e.Location);
            if (index != System.Windows.Forms.ListBox.NoMatches)
            {
                if(MessageBox.Show("是否删除指定项目", "删除",MessageBoxButtons.OKCancel)==DialogResult.OK)
                {
                    m_lbx_titles.Items.RemoveAt(index);
                }
            }
        }

        private void OnBtnAddTitleClick(object sender, EventArgs e)
        {
            if(m_txt_add_title.Text.Length == 0)
            {
                MessageBox.Show("填入内容不能为空");
                return;
            }
            if(m_txt_add_title.Text.IndexOf(',')>=0 
                || m_txt_add_title.Text.IndexOf('\r') >= 0)
            {
                MessageBox.Show("不能包含逗号，换行符");
                return;
            }
            m_lbx_titles.Items.Add(m_txt_add_title.Text);
            m_txt_add_title.Text = "";
        }

        private void OnBtnSaveTitleClick(object sender, EventArgs e)
        {
            string newTitle = "";
            for(int i=0;i<m_lbx_titles.Items.Count;i++)
            {
                if (i > 0)
                {
                    newTitle += ",";
                }
                newTitle += m_lbx_titles.Items[i].ToString();
            }
            if (m_txt_csv_path.Text != _config.CSVFilePath.Value )
            {
                _config.CSVFilePath.Value = m_txt_csv_path.Text;
            }
            _config.CSVDetailTitle.Value = newTitle;
            _config.ChangeConfigEnd();
            Close();
        }

        private void OnBtnSelectCsvPath(object sender, EventArgs e)
        {
            FolderBrowserDialog dlg = new FolderBrowserDialog();
            dlg.Description = "选择CSV保存文件夹";
            if (dlg.ShowDialog() == DialogResult.OK)
            {
                m_txt_csv_path.Text = dlg.SelectedPath;
            }
        }
    }
}
