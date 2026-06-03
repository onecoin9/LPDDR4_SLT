namespace Hsg.View
{
    partial class EMMDlg
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(EMMDlg));
            this.m_lv_dut_abnormal = new System.Windows.Forms.ListView();
            this.panel1 = new System.Windows.Forms.Panel();
            this.label4 = new System.Windows.Forms.Label();
            this.label3 = new System.Windows.Forms.Label();
            this.m_cbx_filter_up_three = new System.Windows.Forms.CheckBox();
            this.m_cbx_filter_up_two = new System.Windows.Forms.CheckBox();
            this.label2 = new System.Windows.Forms.Label();
            this.m_btn_query_last_all = new System.Windows.Forms.Button();
            this.m_btn_clear_all_abnormal = new System.Windows.Forms.Button();
            this.m_btn_clear = new System.Windows.Forms.Button();
            this.m_btn_query_abnormal_all = new System.Windows.Forms.Button();
            this.m_btn_query_abnormal = new System.Windows.Forms.Button();
            this.m_btn_query_last = new System.Windows.Forms.Button();
            this.label1 = new System.Windows.Forms.Label();
            this.m_cbx_box_no = new System.Windows.Forms.ComboBox();
            this.panel1.SuspendLayout();
            this.SuspendLayout();
            // 
            // m_lv_dut_abnormal
            // 
            this.m_lv_dut_abnormal.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.m_lv_dut_abnormal.GridLines = true;
            this.m_lv_dut_abnormal.HideSelection = false;
            this.m_lv_dut_abnormal.Location = new System.Drawing.Point(2, 101);
            this.m_lv_dut_abnormal.Margin = new System.Windows.Forms.Padding(3, 10, 3, 3);
            this.m_lv_dut_abnormal.Name = "m_lv_dut_abnormal";
            this.m_lv_dut_abnormal.Size = new System.Drawing.Size(814, 460);
            this.m_lv_dut_abnormal.Sorting = System.Windows.Forms.SortOrder.Ascending;
            this.m_lv_dut_abnormal.TabIndex = 1;
            this.m_lv_dut_abnormal.UseCompatibleStateImageBehavior = false;
            this.m_lv_dut_abnormal.View = System.Windows.Forms.View.Details;
            this.m_lv_dut_abnormal.MouseDoubleClick += new System.Windows.Forms.MouseEventHandler(this.m_lv_dut_abnormal_MouseDoubleClick);
            // 
            // panel1
            // 
            this.panel1.Controls.Add(this.label4);
            this.panel1.Controls.Add(this.label3);
            this.panel1.Controls.Add(this.m_cbx_filter_up_three);
            this.panel1.Controls.Add(this.m_cbx_filter_up_two);
            this.panel1.Controls.Add(this.label2);
            this.panel1.Controls.Add(this.m_btn_query_last_all);
            this.panel1.Controls.Add(this.m_btn_clear_all_abnormal);
            this.panel1.Controls.Add(this.m_btn_clear);
            this.panel1.Controls.Add(this.m_btn_query_abnormal_all);
            this.panel1.Controls.Add(this.m_btn_query_abnormal);
            this.panel1.Controls.Add(this.m_btn_query_last);
            this.panel1.Controls.Add(this.label1);
            this.panel1.Controls.Add(this.m_cbx_box_no);
            this.panel1.Dock = System.Windows.Forms.DockStyle.Top;
            this.panel1.Location = new System.Drawing.Point(0, 0);
            this.panel1.Name = "panel1";
            this.panel1.Size = new System.Drawing.Size(821, 88);
            this.panel1.TabIndex = 2;
            // 
            // label4
            // 
            this.label4.AutoSize = true;
            this.label4.Location = new System.Drawing.Point(285, 17);
            this.label4.Name = "label4";
            this.label4.Size = new System.Drawing.Size(73, 24);
            this.label4.TabIndex = 5;
            this.label4.Text = "状态:";
            // 
            // label3
            // 
            this.label3.AutoSize = true;
            this.label3.Location = new System.Drawing.Point(285, 59);
            this.label3.Name = "label3";
            this.label3.Size = new System.Drawing.Size(73, 24);
            this.label3.TabIndex = 5;
            this.label3.Text = "异常:";
            // 
            // m_cbx_filter_up_three
            // 
            this.m_cbx_filter_up_three.AutoSize = true;
            this.m_cbx_filter_up_three.Checked = true;
            this.m_cbx_filter_up_three.CheckState = System.Windows.Forms.CheckState.Checked;
            this.m_cbx_filter_up_three.Location = new System.Drawing.Point(536, 14);
            this.m_cbx_filter_up_three.Name = "m_cbx_filter_up_three";
            this.m_cbx_filter_up_three.Size = new System.Drawing.Size(136, 28);
            this.m_cbx_filter_up_three.TabIndex = 4;
            this.m_cbx_filter_up_three.Text = "最低三次";
            this.m_cbx_filter_up_three.UseVisualStyleBackColor = true;
            this.m_cbx_filter_up_three.CheckedChanged += new System.EventHandler(this.m_cbx_filter_up_three_CheckedChanged);
            // 
            // m_cbx_filter_up_two
            // 
            this.m_cbx_filter_up_two.AutoSize = true;
            this.m_cbx_filter_up_two.Location = new System.Drawing.Point(637, 14);
            this.m_cbx_filter_up_two.Name = "m_cbx_filter_up_two";
            this.m_cbx_filter_up_two.Size = new System.Drawing.Size(136, 28);
            this.m_cbx_filter_up_two.TabIndex = 4;
            this.m_cbx_filter_up_two.Text = "最低两次";
            this.m_cbx_filter_up_two.UseVisualStyleBackColor = true;
            this.m_cbx_filter_up_two.CheckedChanged += new System.EventHandler(this.m_cbx_filter_up_two_CheckedChanged);
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.Font = new System.Drawing.Font("新宋体", 9F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label2.Location = new System.Drawing.Point(17, 59);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(328, 18);
            this.label2.TabIndex = 3;
            this.label2.Text = "TC 代表温控板  TB1/TB2 代表通信板";
            // 
            // m_btn_query_last_all
            // 
            this.m_btn_query_last_all.Location = new System.Drawing.Point(439, 5);
            this.m_btn_query_last_all.Name = "m_btn_query_last_all";
            this.m_btn_query_last_all.Size = new System.Drawing.Size(90, 38);
            this.m_btn_query_last_all.TabIndex = 2;
            this.m_btn_query_last_all.Text = "全部最近";
            this.m_btn_query_last_all.UseVisualStyleBackColor = true;
            this.m_btn_query_last_all.Click += new System.EventHandler(this.OnBtnQueryAllClick);
            // 
            // m_btn_clear_all_abnormal
            // 
            this.m_btn_clear_all_abnormal.Location = new System.Drawing.Point(636, 45);
            this.m_btn_clear_all_abnormal.Name = "m_btn_clear_all_abnormal";
            this.m_btn_clear_all_abnormal.Size = new System.Drawing.Size(90, 38);
            this.m_btn_clear_all_abnormal.TabIndex = 2;
            this.m_btn_clear_all_abnormal.Text = "清空所有";
            this.m_btn_clear_all_abnormal.UseVisualStyleBackColor = true;
            this.m_btn_clear_all_abnormal.Click += new System.EventHandler(this.OnBtnClearAllAbnormalClick);
            // 
            // m_btn_clear
            // 
            this.m_btn_clear.Location = new System.Drawing.Point(536, 46);
            this.m_btn_clear.Name = "m_btn_clear";
            this.m_btn_clear.Size = new System.Drawing.Size(90, 38);
            this.m_btn_clear.TabIndex = 2;
            this.m_btn_clear.Text = "清空当前";
            this.m_btn_clear.UseVisualStyleBackColor = true;
            this.m_btn_clear.Click += new System.EventHandler(this.OnBtnClearCurrentAbnormalClick);
            // 
            // m_btn_query_abnormal_all
            // 
            this.m_btn_query_abnormal_all.Location = new System.Drawing.Point(439, 46);
            this.m_btn_query_abnormal_all.Name = "m_btn_query_abnormal_all";
            this.m_btn_query_abnormal_all.Size = new System.Drawing.Size(90, 38);
            this.m_btn_query_abnormal_all.TabIndex = 2;
            this.m_btn_query_abnormal_all.Text = "所有异常";
            this.m_btn_query_abnormal_all.UseVisualStyleBackColor = true;
            this.m_btn_query_abnormal_all.Click += new System.EventHandler(this.OnBtnQueryAllAbnormalClick);
            // 
            // m_btn_query_abnormal
            // 
            this.m_btn_query_abnormal.Location = new System.Drawing.Point(342, 46);
            this.m_btn_query_abnormal.Name = "m_btn_query_abnormal";
            this.m_btn_query_abnormal.Size = new System.Drawing.Size(90, 38);
            this.m_btn_query_abnormal.TabIndex = 2;
            this.m_btn_query_abnormal.Text = "查询异常";
            this.m_btn_query_abnormal.UseVisualStyleBackColor = true;
            this.m_btn_query_abnormal.Click += new System.EventHandler(this.OnQueryAbnormalClick);
            // 
            // m_btn_query_last
            // 
            this.m_btn_query_last.Location = new System.Drawing.Point(342, 5);
            this.m_btn_query_last.Name = "m_btn_query_last";
            this.m_btn_query_last.Size = new System.Drawing.Size(90, 38);
            this.m_btn_query_last.TabIndex = 2;
            this.m_btn_query_last.Text = "查询最近";
            this.m_btn_query_last.UseVisualStyleBackColor = true;
            this.m_btn_query_last.Click += new System.EventHandler(this.m_btn_query_Click);
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Location = new System.Drawing.Point(17, 23);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(148, 24);
            this.label1.TabIndex = 1;
            this.label1.Text = "测试盒编号:";
            // 
            // m_cbx_box_no
            // 
            this.m_cbx_box_no.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.m_cbx_box_no.FormattingEnabled = true;
            this.m_cbx_box_no.Location = new System.Drawing.Point(127, 19);
            this.m_cbx_box_no.Name = "m_cbx_box_no";
            this.m_cbx_box_no.Size = new System.Drawing.Size(130, 32);
            this.m_cbx_box_no.TabIndex = 0;
            // 
            // EMMDlg
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(13F, 24F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(821, 564);
            this.Controls.Add(this.panel1);
            this.Controls.Add(this.m_lv_dut_abnormal);
            this.Font = new System.Drawing.Font("新宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Name = "EMMDlg";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.Text = "设备运维管理";
            this.Load += new System.EventHandler(this.EMMDlg_Load);
            this.panel1.ResumeLayout(false);
            this.panel1.PerformLayout();
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.ListView m_lv_dut_abnormal;
        private System.Windows.Forms.Panel panel1;
        private System.Windows.Forms.ComboBox m_cbx_box_no;
        private System.Windows.Forms.Button m_btn_query_last;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.Button m_btn_query_last_all;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.Button m_btn_query_abnormal_all;
        private System.Windows.Forms.Button m_btn_query_abnormal;
        private System.Windows.Forms.CheckBox m_cbx_filter_up_two;
        private System.Windows.Forms.Button m_btn_clear;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.Button m_btn_clear_all_abnormal;
        private System.Windows.Forms.CheckBox m_cbx_filter_up_three;
    }
}