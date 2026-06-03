namespace Hsg.View
{
    partial class CSVSetting
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(CSVSetting));
            this.m_lbx_titles = new System.Windows.Forms.ListBox();
            this.m_txt_add_title = new System.Windows.Forms.TextBox();
            this.label1 = new System.Windows.Forms.Label();
            this.label2 = new System.Windows.Forms.Label();
            this.m_btn_add = new System.Windows.Forms.Button();
            this.button1 = new System.Windows.Forms.Button();
            this.m_txt_csv_path = new System.Windows.Forms.TextBox();
            this.label3 = new System.Windows.Forms.Label();
            this.button2 = new System.Windows.Forms.Button();
            this.SuspendLayout();
            // 
            // m_lbx_titles
            // 
            this.m_lbx_titles.FormattingEnabled = true;
            this.m_lbx_titles.ItemHeight = 24;
            this.m_lbx_titles.Location = new System.Drawing.Point(12, 40);
            this.m_lbx_titles.Margin = new System.Windows.Forms.Padding(4);
            this.m_lbx_titles.Name = "m_lbx_titles";
            this.m_lbx_titles.Size = new System.Drawing.Size(484, 196);
            this.m_lbx_titles.TabIndex = 0;
            this.m_lbx_titles.MouseDoubleClick += new System.Windows.Forms.MouseEventHandler(this.OnMouseDoubleClick);
            // 
            // m_txt_add_title
            // 
            this.m_txt_add_title.Location = new System.Drawing.Point(82, 268);
            this.m_txt_add_title.Margin = new System.Windows.Forms.Padding(4);
            this.m_txt_add_title.Name = "m_txt_add_title";
            this.m_txt_add_title.Size = new System.Drawing.Size(192, 35);
            this.m_txt_add_title.TabIndex = 1;
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label1.Location = new System.Drawing.Point(177, 9);
            this.label1.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(162, 24);
            this.label1.TabIndex = 2;
            this.label1.Text = "CSV 表头编辑";
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.Location = new System.Drawing.Point(12, 274);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(70, 24);
            this.label2.TabIndex = 3;
            this.label2.Text = "名称:";
            // 
            // m_btn_add
            // 
            this.m_btn_add.Location = new System.Drawing.Point(300, 265);
            this.m_btn_add.Name = "m_btn_add";
            this.m_btn_add.Size = new System.Drawing.Size(95, 33);
            this.m_btn_add.TabIndex = 4;
            this.m_btn_add.Text = "添加";
            this.m_btn_add.UseVisualStyleBackColor = true;
            this.m_btn_add.Click += new System.EventHandler(this.OnBtnAddTitleClick);
            // 
            // button1
            // 
            this.button1.Location = new System.Drawing.Point(400, 265);
            this.button1.Name = "button1";
            this.button1.Size = new System.Drawing.Size(95, 33);
            this.button1.TabIndex = 4;
            this.button1.Text = "保存";
            this.button1.UseVisualStyleBackColor = true;
            this.button1.Click += new System.EventHandler(this.OnBtnSaveTitleClick);
            // 
            // m_txt_csv_path
            // 
            this.m_txt_csv_path.Location = new System.Drawing.Point(94, 311);
            this.m_txt_csv_path.Margin = new System.Windows.Forms.Padding(4);
            this.m_txt_csv_path.Name = "m_txt_csv_path";
            this.m_txt_csv_path.RightToLeft = System.Windows.Forms.RightToLeft.Yes;
            this.m_txt_csv_path.Size = new System.Drawing.Size(300, 35);
            this.m_txt_csv_path.TabIndex = 1;
            // 
            // label3
            // 
            this.label3.AutoSize = true;
            this.label3.Location = new System.Drawing.Point(12, 317);
            this.label3.Name = "label3";
            this.label3.Size = new System.Drawing.Size(118, 24);
            this.label3.TabIndex = 3;
            this.label3.Text = "存储路径:";
            // 
            // button2
            // 
            this.button2.Location = new System.Drawing.Point(401, 309);
            this.button2.Name = "button2";
            this.button2.Size = new System.Drawing.Size(95, 33);
            this.button2.TabIndex = 4;
            this.button2.Text = "选择路径";
            this.button2.UseVisualStyleBackColor = true;
            this.button2.Click += new System.EventHandler(this.OnBtnSelectCsvPath);
            // 
            // CSVSetting
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(12F, 24F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(523, 356);
            this.Controls.Add(this.button1);
            this.Controls.Add(this.button2);
            this.Controls.Add(this.m_btn_add);
            this.Controls.Add(this.label3);
            this.Controls.Add(this.label2);
            this.Controls.Add(this.label1);
            this.Controls.Add(this.m_txt_csv_path);
            this.Controls.Add(this.m_txt_add_title);
            this.Controls.Add(this.m_lbx_titles);
            this.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(4);
            this.Name = "CSVSetting";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.Text = "SCVSetting";
            this.Load += new System.EventHandler(this.SCVSetting_Load);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.ListBox m_lbx_titles;
        private System.Windows.Forms.TextBox m_txt_add_title;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.Button m_btn_add;
        private System.Windows.Forms.Button button1;
        private System.Windows.Forms.TextBox m_txt_csv_path;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.Button button2;
    }
}