namespace Hsg.View
{
    partial class WorkOrderDlg
    {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(WorkOrderDlg));
            this.m_btn_confirm = new System.Windows.Forms.Button();
            this.m_btn_create = new System.Windows.Forms.Button();
            this.m_btn_delete = new System.Windows.Forms.Button();
            this.m_lv_workOrderList = new System.Windows.Forms.ListView();
            this.panel1 = new System.Windows.Forms.Panel();
            this.panel4 = new System.Windows.Forms.Panel();
            this.m_btn_close = new System.Windows.Forms.Button();
            this.panel3 = new System.Windows.Forms.Panel();
            this.panel2 = new System.Windows.Forms.Panel();
            this.panel1.SuspendLayout();
            this.panel4.SuspendLayout();
            this.SuspendLayout();
            // 
            // m_btn_confirm
            // 
            this.m_btn_confirm.Location = new System.Drawing.Point(74, 9);
            this.m_btn_confirm.Margin = new System.Windows.Forms.Padding(4);
            this.m_btn_confirm.Name = "m_btn_confirm";
            this.m_btn_confirm.Size = new System.Drawing.Size(139, 59);
            this.m_btn_confirm.TabIndex = 1;
            this.m_btn_confirm.Text = "确定";
            this.m_btn_confirm.UseVisualStyleBackColor = true;
            this.m_btn_confirm.Click += new System.EventHandler(this.m_btn_confirm_Click);
            // 
            // m_btn_create
            // 
            this.m_btn_create.Location = new System.Drawing.Point(238, 9);
            this.m_btn_create.Margin = new System.Windows.Forms.Padding(4);
            this.m_btn_create.Name = "m_btn_create";
            this.m_btn_create.Size = new System.Drawing.Size(139, 59);
            this.m_btn_create.TabIndex = 1;
            this.m_btn_create.Text = "新建";
            this.m_btn_create.UseVisualStyleBackColor = true;
            this.m_btn_create.Click += new System.EventHandler(this.m_btn_create_Click);
            // 
            // m_btn_delete
            // 
            this.m_btn_delete.Location = new System.Drawing.Point(566, 9);
            this.m_btn_delete.Margin = new System.Windows.Forms.Padding(4);
            this.m_btn_delete.Name = "m_btn_delete";
            this.m_btn_delete.Size = new System.Drawing.Size(139, 59);
            this.m_btn_delete.TabIndex = 1;
            this.m_btn_delete.Text = "删除";
            this.m_btn_delete.UseVisualStyleBackColor = true;
            this.m_btn_delete.Click += new System.EventHandler(this.m_btn_delete_Click);
            // 
            // m_lv_workOrderList
            // 
            this.m_lv_workOrderList.BorderStyle = System.Windows.Forms.BorderStyle.None;
            this.m_lv_workOrderList.Dock = System.Windows.Forms.DockStyle.Top;
            this.m_lv_workOrderList.Font = new System.Drawing.Font("新宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_lv_workOrderList.GridLines = true;
            this.m_lv_workOrderList.HideSelection = false;
            this.m_lv_workOrderList.Location = new System.Drawing.Point(0, 0);
            this.m_lv_workOrderList.Name = "m_lv_workOrderList";
            this.m_lv_workOrderList.OwnerDraw = true;
            this.m_lv_workOrderList.Size = new System.Drawing.Size(1113, 228);
            this.m_lv_workOrderList.TabIndex = 3;
            this.m_lv_workOrderList.UseCompatibleStateImageBehavior = false;
            this.m_lv_workOrderList.View = System.Windows.Forms.View.Details;
            this.m_lv_workOrderList.ColumnClick += new System.Windows.Forms.ColumnClickEventHandler(this.m_lv_workOrderList_ColumnClick);
            this.m_lv_workOrderList.DrawColumnHeader += new System.Windows.Forms.DrawListViewColumnHeaderEventHandler(this.WorkOrderList_DrawColumnHeader);
            this.m_lv_workOrderList.DrawItem += new System.Windows.Forms.DrawListViewItemEventHandler(this.WorkOrderList_DrawItem);
            this.m_lv_workOrderList.DrawSubItem += new System.Windows.Forms.DrawListViewSubItemEventHandler(this.WorkOrderList_DrawSubItem);
            // 
            // panel1
            // 
            this.panel1.Controls.Add(this.panel4);
            this.panel1.Controls.Add(this.panel3);
            this.panel1.Controls.Add(this.panel2);
            this.panel1.Dock = System.Windows.Forms.DockStyle.Bottom;
            this.panel1.Location = new System.Drawing.Point(0, 302);
            this.panel1.Name = "panel1";
            this.panel1.Size = new System.Drawing.Size(1113, 84);
            this.panel1.TabIndex = 4;
            // 
            // panel4
            // 
            this.panel4.Anchor = System.Windows.Forms.AnchorStyles.Top;
            this.panel4.Controls.Add(this.m_btn_confirm);
            this.panel4.Controls.Add(this.m_btn_close);
            this.panel4.Controls.Add(this.m_btn_delete);
            this.panel4.Controls.Add(this.m_btn_create);
            this.panel4.Location = new System.Drawing.Point(167, 3);
            this.panel4.Name = "panel4";
            this.panel4.Size = new System.Drawing.Size(779, 78);
            this.panel4.TabIndex = 0;
            // 
            // m_btn_close
            // 
            this.m_btn_close.Location = new System.Drawing.Point(402, 9);
            this.m_btn_close.Margin = new System.Windows.Forms.Padding(4);
            this.m_btn_close.Name = "m_btn_close";
            this.m_btn_close.Size = new System.Drawing.Size(139, 59);
            this.m_btn_close.TabIndex = 1;
            this.m_btn_close.Text = "关闭工单";
            this.m_btn_close.UseVisualStyleBackColor = true;
            this.m_btn_close.Click += new System.EventHandler(this.m_btn_close_Click);
            // 
            // panel3
            // 
            this.panel3.Anchor = ((System.Windows.Forms.AnchorStyles)(((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.panel3.Location = new System.Drawing.Point(705, 3);
            this.panel3.Name = "panel3";
            this.panel3.Size = new System.Drawing.Size(405, 78);
            this.panel3.TabIndex = 0;
            // 
            // panel2
            // 
            this.panel2.Anchor = ((System.Windows.Forms.AnchorStyles)(((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.panel2.Location = new System.Drawing.Point(0, 0);
            this.panel2.Name = "panel2";
            this.panel2.Size = new System.Drawing.Size(405, 84);
            this.panel2.TabIndex = 0;
            // 
            // WorkOrderDlg
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(13F, 24F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(1113, 386);
            this.Controls.Add(this.panel1);
            this.Controls.Add(this.m_lv_workOrderList);
            this.Font = new System.Drawing.Font("新宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(4);
            this.MaximizeBox = false;
            this.Name = "WorkOrderDlg";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.Text = "工单选择和设置";
            this.Load += new System.EventHandler(this.WorkOrderDlg_Load);
            this.panel1.ResumeLayout(false);
            this.panel4.ResumeLayout(false);
            this.ResumeLayout(false);

        }

        #endregion
        private System.Windows.Forms.Button m_btn_confirm;
        private System.Windows.Forms.Button m_btn_create;
        private System.Windows.Forms.Button m_btn_delete;
        private System.Windows.Forms.ListView m_lv_workOrderList;
        private System.Windows.Forms.Panel panel1;
        private System.Windows.Forms.Panel panel4;
        private System.Windows.Forms.Panel panel3;
        private System.Windows.Forms.Panel panel2;
        private System.Windows.Forms.Button m_btn_close;
    }
}