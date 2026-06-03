namespace Hsg.View
{
    partial class TempReparation
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(TempReparation));
            this.panel1 = new System.Windows.Forms.Panel();
            this.m_lab_change = new System.Windows.Forms.Label();
            this.label1 = new System.Windows.Forms.Label();
            this.m_cbx_box_no = new System.Windows.Forms.ComboBox();
            this.m_viewText = new System.Windows.Forms.TextBox();
            this.m_lv_reparation = new System.Windows.Forms.ListView();
            this.m_btn_return = new System.Windows.Forms.Button();
            this.m_btn_save = new System.Windows.Forms.Button();
            this.btn_reset_temp = new System.Windows.Forms.Button();
            this.panel1.SuspendLayout();
            this.SuspendLayout();
            // 
            // panel1
            // 
            this.panel1.Controls.Add(this.m_lab_change);
            this.panel1.Controls.Add(this.label1);
            this.panel1.Controls.Add(this.m_cbx_box_no);
            this.panel1.Dock = System.Windows.Forms.DockStyle.Top;
            this.panel1.Location = new System.Drawing.Point(0, 0);
            this.panel1.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.panel1.Name = "panel1";
            this.panel1.Size = new System.Drawing.Size(890, 69);
            this.panel1.TabIndex = 3;
            // 
            // m_lab_change
            // 
            this.m_lab_change.AutoSize = true;
            this.m_lab_change.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_lab_change.ForeColor = System.Drawing.Color.OrangeRed;
            this.m_lab_change.Location = new System.Drawing.Point(636, 22);
            this.m_lab_change.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.m_lab_change.Name = "m_lab_change";
            this.m_lab_change.Size = new System.Drawing.Size(130, 24);
            this.m_lab_change.TabIndex = 2;
            this.m_lab_change.Text = "修改未保存";
            this.m_lab_change.Visible = false;
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label1.Location = new System.Drawing.Point(147, 24);
            this.label1.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(94, 24);
            this.label1.TabIndex = 1;
            this.label1.Text = "测试盒:";
            // 
            // m_cbx_box_no
            // 
            this.m_cbx_box_no.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.m_cbx_box_no.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_cbx_box_no.FormattingEnabled = true;
            this.m_cbx_box_no.Location = new System.Drawing.Point(252, 18);
            this.m_cbx_box_no.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.m_cbx_box_no.Name = "m_cbx_box_no";
            this.m_cbx_box_no.Size = new System.Drawing.Size(344, 32);
            this.m_cbx_box_no.TabIndex = 0;
            this.m_cbx_box_no.SelectedIndexChanged += new System.EventHandler(this.m_cbx_box_no_SelectedIndexChanged);
            this.m_cbx_box_no.Click += new System.EventHandler(this.m_cbx_box_no_Click);
            // 
            // m_viewText
            // 
            this.m_viewText.BorderStyle = System.Windows.Forms.BorderStyle.None;
            this.m_viewText.Location = new System.Drawing.Point(710, 678);
            this.m_viewText.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.m_viewText.Name = "m_viewText";
            this.m_viewText.Size = new System.Drawing.Size(150, 21);
            this.m_viewText.TabIndex = 2;
            this.m_viewText.Text = "123";
            this.m_viewText.Visible = false;
            // 
            // m_lv_reparation
            // 
            this.m_lv_reparation.Font = new System.Drawing.Font("宋体", 9F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_lv_reparation.FullRowSelect = true;
            this.m_lv_reparation.GridLines = true;
            this.m_lv_reparation.HideSelection = false;
            this.m_lv_reparation.Location = new System.Drawing.Point(0, 78);
            this.m_lv_reparation.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.m_lv_reparation.MultiSelect = false;
            this.m_lv_reparation.Name = "m_lv_reparation";
            this.m_lv_reparation.Size = new System.Drawing.Size(882, 637);
            this.m_lv_reparation.TabIndex = 0;
            this.m_lv_reparation.UseCompatibleStateImageBehavior = false;
            this.m_lv_reparation.View = System.Windows.Forms.View.Details;
            this.m_lv_reparation.MouseDoubleClick += new System.Windows.Forms.MouseEventHandler(this.m_lv_reparation_MouseDoubleClick);
            // 
            // m_btn_return
            // 
            this.m_btn_return.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_btn_return.Location = new System.Drawing.Point(640, 726);
            this.m_btn_return.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.m_btn_return.Name = "m_btn_return";
            this.m_btn_return.Size = new System.Drawing.Size(174, 51);
            this.m_btn_return.TabIndex = 3;
            this.m_btn_return.Text = "返回";
            this.m_btn_return.UseVisualStyleBackColor = true;
            this.m_btn_return.Click += new System.EventHandler(this.m_btn_return_Click);
            // 
            // m_btn_save
            // 
            this.m_btn_save.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_btn_save.Location = new System.Drawing.Point(192, 726);
            this.m_btn_save.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.m_btn_save.Name = "m_btn_save";
            this.m_btn_save.Size = new System.Drawing.Size(174, 51);
            this.m_btn_save.TabIndex = 4;
            this.m_btn_save.Text = "保存";
            this.m_btn_save.UseVisualStyleBackColor = true;
            this.m_btn_save.Click += new System.EventHandler(this.OnBtnSave);
            // 
            // btn_reset_temp
            // 
            this.btn_reset_temp.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.btn_reset_temp.Location = new System.Drawing.Point(410, 726);
            this.btn_reset_temp.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.btn_reset_temp.Name = "btn_reset_temp";
            this.btn_reset_temp.Size = new System.Drawing.Size(174, 51);
            this.btn_reset_temp.TabIndex = 4;
            this.btn_reset_temp.Text = "重置温度";
            this.btn_reset_temp.UseVisualStyleBackColor = true;
            this.btn_reset_temp.Click += new System.EventHandler(this.OnBtnResetTemp);
            // 
            // TempReparation
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(9F, 18F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(890, 795);
            this.Controls.Add(this.m_viewText);
            this.Controls.Add(this.m_btn_return);
            this.Controls.Add(this.panel1);
            this.Controls.Add(this.btn_reset_temp);
            this.Controls.Add(this.m_btn_save);
            this.Controls.Add(this.m_lv_reparation);
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "TempReparation";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.Text = "TempReparation";
            this.Load += new System.EventHandler(this.TempReparation_Load);
            this.panel1.ResumeLayout(false);
            this.panel1.PerformLayout();
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion
        private System.Windows.Forms.Panel panel1;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.ComboBox m_cbx_box_no;
        private System.Windows.Forms.ListView m_lv_reparation;
        private System.Windows.Forms.Button m_btn_return;
        private System.Windows.Forms.Button m_btn_save;
        private System.Windows.Forms.TextBox m_viewText;
        private System.Windows.Forms.Label m_lab_change;
        private System.Windows.Forms.Button btn_reset_temp;
    }
}