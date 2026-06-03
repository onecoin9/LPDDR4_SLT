using Hsg.BLL;
using Hsg.Common;
using Hsg.Common.ADO;
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
    public partial class WorkOrderDlg : Form
    {
        private DBHandler _dbHandler;
        private DataTable _workOrderTable;
        public int SelectWorkOrderId = 0;
        private bool _isOnline;// 是否是在线模式
        public WorkOrderDlg(bool isOnline)
        {
            InitializeComponent();
            _dbHandler = DBHandler.Instance;
            m_lv_workOrderList.View = System.Windows.Forms.View.Details;
            m_lv_workOrderList.FullRowSelect = true;
            m_lv_workOrderList.Columns.Add("工序", 100);
            m_lv_workOrderList.Columns.Add("环境", 100);
            m_lv_workOrderList.Columns.Add("订单编号", 180);
            m_lv_workOrderList.Columns.Add("物料编号", 180);
            m_lv_workOrderList.Columns.Add("测试方案", 400);
            _isOnline = isOnline;

        }

        private void LoadWorkOrderDataTable()
        {
            DataSet set = _dbHandler.QueryWorkOrderView();
            _workOrderTable = set.Tables[0];
            m_lv_workOrderList.Items.Clear();
            for (int i = 0; i < _workOrderTable.Rows.Count; i++)
            {
                DataRow row = _workOrderTable.Rows[i];
                ListViewItem item = new ListViewItem(row["workStageDescription"].ToString());
                string tempStateStr = DBTableColumn.TempStateToString(byte.Parse(row["tmpState"].ToString()));
                item.SubItems.Add(tempStateStr);
                item.SubItems.Add(row["orderNo"].ToString());
                item.SubItems.Add(row["materialNo"].ToString());
                item.SubItems.Add(row["policyName"].ToString());
                m_lv_workOrderList.Items.Add(item);
            }

            AutoResizeColumns(m_lv_workOrderList);
        }

        private void m_lv_workOrderList_ColumnClick(object sender, ColumnClickEventArgs e)
        {

        }

        private void AutoResizeColumns(ListView listView)
        {
            listView.BeginUpdate(); // 开始更新，‌减少闪烁并提高性能

            try
            {
                foreach (ColumnHeader column in listView.Columns)
                {
                    // 设置列的宽度为自动调整
                    column.Width = -2;
                }

                // 遍历所有项，‌以确保考虑到了所有内容
                foreach (ListViewItem item in listView.Items)
                {
                    // 再次遍历所有列，‌确保每列都被调整
                    foreach (ColumnHeader column in listView.Columns)
                    {
                        // 使用AutoResizeColumn方法自动调整列宽
                        listView.AutoResizeColumn(column.Index, ColumnHeaderAutoResizeStyle.HeaderSize);
                        // 或者，‌如果你想要列宽完全适应内容，‌可以使用以下代码：‌
                        // listView.AutoResizeColumn(column.Index, ColumnHeaderAutoResizeStyle.ColumnContent);
                    }
                }
            }
            finally
            {
                listView.EndUpdate(); // 结束更新
            }
        }
        private void m_btn_confirm_Click(object sender, EventArgs e)
        {

            int selectCount = m_lv_workOrderList.SelectedItems.Count;
            if (selectCount > 0)
            {
                // 获取选中行的索引

                int selectedIndex = m_lv_workOrderList.SelectedItems[0].Index;
                DataRow row = _workOrderTable.Rows[selectedIndex];

                //  string workStageName = row["workStageName"].ToString();
                string workStageId = row["workStageId"].ToString();
                string workStageDescription = "";
                string workStageName = "";
                WorkStage.GetStageInfo(int.Parse(workStageId), ref workStageName, ref workStageDescription);
                //string workStageDescription = row["workStageDescription"].ToString();
                string workOrderNo = row["workOrderNo"].ToString() + "-";
                workOrderNo += DateTime.Now.ToString("yyyy_MM_dd");// 使用母单ID + 日期
                string workOrderId = row["workOrderId"].ToString();
                string materialNo = row["materialNo"].ToString();
                string orderNo = row["orderNo"].ToString();
                string TmpState = row["TmpState"].ToString();
                string addTotal = row["addTotal"].ToString();
                string addPass = row["addPass"].ToString();
                string policyName = row["policyName"].ToString();
                string policyFullPath = Path.Combine(SysConfig.PolicyFolderPath, policyName) + SysConfig.PolicyFileExtName;
                if (!File.Exists(policyFullPath))
                {
                    MessageBox.Show("测试方案不存在");
                    return;
                }
                string errorMsg = "";
                if (PolicyFile.Deserialize(policyFullPath, ref errorMsg) == null)
                {
                    MessageBox.Show("测试方案格式错误或者文件损坏");
                    return;
                }
                //SelectWorkOrderId = Int32.Parse(workOrderId);
                //string orderNo = "";
                //string materialNo = "";
                //string workOrderNo = "";
                //byte[] testCfg = Array.Empty<byte>();
                //string cfgName = "";
                //byte TmpState = 0;
                //int timeoutMinute = 0;
                //string cfgDescription = "";
                //if (_dbHandler.QueryWorkOrderInfor(int.Parse(workOrderId), ref orderNo, ref materialNo, ref workOrderNo, ref testCfg, ref cfgName, ref TmpState, ref timeoutMinute, ref cfgDescription))
                //{

                //}
                //// 获取并显示选中行的第一列内容
                //string selectedText = m_lv_workOrderList.SelectedItems[0].Text;
                //MessageBox.Show("选中的行索引: " + selectedIndex + ", 内容: " + selectedText);

                //// 如果需要获取选中行的其他列内容，‌可以使用以下方式
                //foreach (ListViewItem.ListViewSubItem subItem in m_lv_workOrderList.SelectedItems[0].SubItems)
                //{
                //    MessageBox.Show("列内容: " + subItem.Text);
                //}

                if (_isOnline)
                {
                    SysConfig.SetWorkOrderDetail(WorkMode.Online, workStageDescription, workStageName, int.Parse(workOrderId), workOrderNo, orderNo, materialNo, byte.Parse(TmpState));
                }
                else
                {
                    SysConfig.SetWorkOrderDetail(WorkMode.OffLine, workStageDescription, workStageName, int.Parse(workOrderId), workOrderNo, orderNo, materialNo, byte.Parse(TmpState), bool.Parse(addTotal), bool.Parse(addPass), policyName);
                }
                DialogResult = DialogResult.OK;
                Close();
            }
            else
            {
                MessageBox.Show("未选择有效的工单");
            }
        }

        private void m_btn_create_Click(object sender, EventArgs e)
        {
            WorkOrderAddDlg dlg = new WorkOrderAddDlg();
            if (dlg.ShowDialog() == DialogResult.OK)
            {
                LoadWorkOrderDataTable();
            }
        }


        private void WorkOrderList_DrawColumnHeader(object sender, DrawListViewColumnHeaderEventArgs e)
        {
            e.DrawDefault = false;

            // 设置列标题的颜色为红色
            e.Graphics.FillRectangle(Brushes.LightBlue, e.Bounds);
            TextRenderer.DrawText(e.Graphics, e.Header.Text, m_lv_workOrderList.Font, e.Bounds, Color.DarkBlue, TextFormatFlags.VerticalCenter | TextFormatFlags.Left);
        }

        private void WorkOrderList_DrawItem(object sender, DrawListViewItemEventArgs e)
        {
            e.DrawDefault = true;
        }

        private void WorkOrderList_DrawSubItem(object sender, DrawListViewSubItemEventArgs e)
        {
            e.DrawDefault = true;
        }

        private void m_btn_delete_Click(object sender, EventArgs e)
        {
            Password pwd = new Password("10086");
            int selectCount = m_lv_workOrderList.SelectedItems.Count;
            if (selectCount > 0)
            {
                // 获取选中行的索引
                int selectedIndex = m_lv_workOrderList.SelectedItems[0].Index;
                DataRow row = _workOrderTable.Rows[selectedIndex];
                string workOrderId = row["workOrderId"].ToString();
                if (pwd.ShowDialog() == DialogResult.OK)
                {
                    if (_dbHandler.DeleteWorkOrder(Int32.Parse(workOrderId)))
                    {
                        LoadWorkOrderDataTable();
                    }
                    else
                    {
                        MessageBox.Show("删除失败");
                    }
                }
            }
            else
            {
                MessageBox.Show("未选择有效的工单");
            }
        }

        private void m_btn_close_Click(object sender, EventArgs e)
        {
            Password pwd = new Password("10086");
            int selectCount = m_lv_workOrderList.SelectedItems.Count;
            if (selectCount > 0)
            {
                // 获取选中行的索引
                int selectedIndex = m_lv_workOrderList.SelectedItems[0].Index;
                DataRow row = _workOrderTable.Rows[selectedIndex];
                string workOrderId = row["workOrderId"].ToString();
                if (pwd.ShowDialog() == DialogResult.OK)
                {
                    if (_dbHandler.CloseWorkOrder(Int32.Parse(workOrderId)))
                    {
                        LoadWorkOrderDataTable();
                    }
                    else
                    {
                        MessageBox.Show("关闭失败");
                    }
                }
            }
            else
            {
                MessageBox.Show("未选择有效的工单");
            }
        }

        private void WorkOrderDlg_Load(object sender, EventArgs e)
        {
            if (!_dbHandler.LoadDataBase())
            {
                MessageBox.Show("数据文件损坏，程序无法使用");
                Close();
            }
            else
            {
                LoadWorkOrderDataTable();
            }
        }
    }
}
