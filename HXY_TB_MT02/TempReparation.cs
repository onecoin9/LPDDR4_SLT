using Hsg.BLL;
using Hsg.BLL.config;
using Hsg.BLL.Model;
using Hsg.BLL.TempCtr;
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
    public partial class TempReparation : Form
    {
        private SysConfig _config;
        //  private TextBox editTextBox;
        private ListViewItem currentItem;
        private int currentSubItemIndex;
        private bool _changeFlag = false;
        private int _lastSelectBoxIndex = 0;
        private BSController _bsController;
        public TempReparation(BSController bsControl )
        {
            InitializeComponent();
            m_lv_reparation.Columns.Add("测试盒", 100);
            m_lv_reparation.Columns.Add("Dut", 180);
            m_lv_reparation.Columns.Add("补偿值");
            for (int i = 0; i < SysConfig.DEV_NUM; i++)
            {
                int no = i + 1;
                m_cbx_box_no.Items.Add(no.ToString("D2"));
            }
            m_cbx_box_no.SelectedIndex = _lastSelectBoxIndex;
            _config = SysConfig.GetInstance();

            m_viewText.KeyDown += EditTextBox_KeyDown;
            m_viewText.LostFocus += EditTextBox_LostFocus;
            m_viewText.Visible = false;
            _bsController = bsControl;
        }
        public void LoadSelectedSiteReparation()
        {
            m_lv_reparation.Items.Clear();
            ListViewItem item = null;
            int index = m_cbx_box_no.SelectedIndex;
            if (index < 0)
            {
                return;
            }
            _lastSelectBoxIndex = index;
            TempCtrBoardConfig config = new TempCtrBoardConfig(index);
            for (int i = 0; i < TempProtocol.ONE_TEAM_DUT_NUM; i++)
            {
                item = new ListViewItem((index + 1).ToString("D2"));

                item.SubItems.Add((i + 1).ToString("D2"));
                item.SubItems.Add(config.GetDutTempCompensator(i).ToString("F1"));
                m_lv_reparation.Items.Add(item);
            }
        }

        private void TempReparation_Load(object sender, EventArgs e)
        {
            LoadSelectedSiteReparation();
        }

        private void m_cbx_box_no_SelectedIndexChanged(object sender, EventArgs e)
        {
            if (_changeFlag)
            {
                if (MessageBox.Show("当前存在修改未保存,是否保存", "修改提示", MessageBoxButtons.YesNo) == DialogResult.Yes)
                {
                    SaveTempReparation(_lastSelectBoxIndex);
                }
                else
                {
                    m_lab_change.Visible = false;
                    _changeFlag = false;
                }
            }
            LoadSelectedSiteReparation();
        }
        private int GetSubItemIndexAt(int x, int y)
        {
            int left = m_lv_reparation.Margin.Left + m_lv_reparation.Left;
            int right = 0;
            for (int i = 0; i < m_lv_reparation.Columns.Count; i++)
            {
                left = right;
                right += m_lv_reparation.Columns[i].Width;
                if (x >= left && x < right)
                {
                    return i;
                }
            }
            return -1;
        }

        private void ShowEditTextBox(ListViewItem item, int subItemIndex)
        {
            Rectangle itemRect = item.Bounds;
            //itemRect.X += m_lv_reparation.Columns[subItemIndex].Width * subItemIndex;
            itemRect.X += m_lv_reparation.Margin.Left + m_lv_reparation.Left+2;
            for (int i = 0; i < subItemIndex; i++)
            {
                itemRect.X += m_lv_reparation.Columns[i].Width;
            }
            itemRect.Y += m_lv_reparation.Margin.Top + m_lv_reparation.Top;
            itemRect.Width = m_lv_reparation.Columns[subItemIndex].Width-2;
            itemRect.Height = item.Bounds.Height;

            m_viewText.Bounds = itemRect;
            m_viewText.Text = item.SubItems[subItemIndex].Text;
            m_viewText.Visible = true;
            m_viewText.Focus();
        }

        private void EditTextBox_KeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Enter)
            {
                UpdateListViewItem();
                m_viewText.Visible = false;
            }
        }

        private void EditTextBox_LostFocus(object sender, EventArgs e)
        {
            UpdateListViewItem();
            m_viewText.Visible = false;
        }

        private void UpdateListViewItem()
        {
            if (currentItem != null && currentSubItemIndex >= 0)
            {
                float value = 0;
                if (float.TryParse(m_viewText.Text, out value))
                {
                    string SetValue = value.ToString("F1");
                    if(SetValue  != currentItem.SubItems[currentSubItemIndex].Text)
                    {
                        currentItem.SubItems[currentSubItemIndex].Text = SetValue;
                        OnChange();
                    }
                    
                }
            }
        }

        private void m_lv_reparation_MouseDoubleClick(object sender, MouseEventArgs e)
        {
            if (m_lv_reparation.SelectedItems.Count == 0) return;
            MouseEventArgs me = (MouseEventArgs)e;
            currentItem = m_lv_reparation.SelectedItems[0];
            currentSubItemIndex = GetSubItemIndexAt(me.X, me.Y);

            if (currentSubItemIndex == 2)
            {
                ShowEditTextBox(currentItem, currentSubItemIndex);
            }
        }

        private void OnBtnSave(object sender, EventArgs e)
        {
            SaveTempReparation(m_cbx_box_no.SelectedIndex);
            if(MessageBox.Show("是否立马重置环境温度(测试中勿用)","重置温度", MessageBoxButtons.YesNo) == DialogResult.Yes)
            {
                _bsController.RefreshEnverionment(m_cbx_box_no.SelectedIndex);
            }
        }

        private void SaveTempReparation(int selectSiteIndex)
        {
            string value = "";
            if (selectSiteIndex < 0)
                return;
            for (int i = 0; i < m_lv_reparation.Items.Count; i++)
            {
                if (value.Length > 0)
                {
                    value += ",";
                }
                ListViewItem item = m_lv_reparation.Items[i];
                value += item.SubItems[2].Text;
            }
            _config.SiteTempReparation.SetItem(selectSiteIndex, value);
            _config.ConfigSave();
            _changeFlag = false;
            m_lab_change.Visible = false;
        }

        private void OnChange()
        {
            m_lab_change.Visible = true;
            _changeFlag = true;
        }

        private void m_btn_return_Click(object sender, EventArgs e)
        {
            Close();
        }

        private void m_cbx_box_no_Click(object sender, EventArgs e)
        {
            
        }

        private void OnBtnResetTemp(object sender, EventArgs e)
        {
            if(_changeFlag)
            {
                MessageBox.Show("请先保存修改，才能能重置更新");
                return;
            }
            if(m_cbx_box_no.SelectedIndex <0)
            {
                MessageBox.Show("请选择操作的测试盒");
                return;
            }
            if (MessageBox.Show("是否立马重置环境温度(测试中勿用)", "重置温度", MessageBoxButtons.YesNo) == DialogResult.Yes)
            {
                _bsController.RefreshEnverionment(m_cbx_box_no.SelectedIndex);
            }
        }
    }
}
