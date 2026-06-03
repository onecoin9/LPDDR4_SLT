namespace Hsg.View
{
    partial class EditPolicyDlg
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(EditPolicyDlg));
            this.m_pal_policy_list = new System.Windows.Forms.FlowLayoutPanel();
            this.panel1 = new System.Windows.Forms.Panel();
            this.txt_sub_path = new System.Windows.Forms.TextBox();
            this.rbt_mixture_tmp = new System.Windows.Forms.RadioButton();
            this.rbt_hight_tmp = new System.Windows.Forms.RadioButton();
            this.rbt_normal_tmp = new System.Windows.Forms.RadioButton();
            this.label2 = new System.Windows.Forms.Label();
            this.txt_policy_name = new System.Windows.Forms.TextBox();
            this.label3 = new System.Windows.Forms.Label();
            this.label1 = new System.Windows.Forms.Label();
            this.m_btn_select_dir = new System.Windows.Forms.Button();
            this.btn_save = new System.Windows.Forms.Button();
            this.panel1.SuspendLayout();
            this.SuspendLayout();
            // 
            // m_pal_policy_list
            // 
            this.m_pal_policy_list.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.m_pal_policy_list.AutoScroll = true;
            this.m_pal_policy_list.Location = new System.Drawing.Point(0, 230);
            this.m_pal_policy_list.Margin = new System.Windows.Forms.Padding(45, 4, 15, 4);
            this.m_pal_policy_list.Name = "m_pal_policy_list";
            this.m_pal_policy_list.Padding = new System.Windows.Forms.Padding(45, 0, 0, 0);
            this.m_pal_policy_list.Size = new System.Drawing.Size(1132, 644);
            this.m_pal_policy_list.TabIndex = 0;
            // 
            // panel1
            // 
            this.panel1.Controls.Add(this.txt_sub_path);
            this.panel1.Controls.Add(this.rbt_mixture_tmp);
            this.panel1.Controls.Add(this.rbt_hight_tmp);
            this.panel1.Controls.Add(this.rbt_normal_tmp);
            this.panel1.Controls.Add(this.label2);
            this.panel1.Controls.Add(this.txt_policy_name);
            this.panel1.Controls.Add(this.label3);
            this.panel1.Controls.Add(this.label1);
            this.panel1.Controls.Add(this.m_btn_select_dir);
            this.panel1.Controls.Add(this.btn_save);
            this.panel1.Dock = System.Windows.Forms.DockStyle.Top;
            this.panel1.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.panel1.Location = new System.Drawing.Point(0, 0);
            this.panel1.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.panel1.Name = "panel1";
            this.panel1.Size = new System.Drawing.Size(1132, 220);
            this.panel1.TabIndex = 1;
            // 
            // txt_sub_path
            // 
            this.txt_sub_path.Location = new System.Drawing.Point(150, 34);
            this.txt_sub_path.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.txt_sub_path.Name = "txt_sub_path";
            this.txt_sub_path.ReadOnly = true;
            this.txt_sub_path.Size = new System.Drawing.Size(796, 35);
            this.txt_sub_path.TabIndex = 7;
            // 
            // rbt_mixture_tmp
            // 
            this.rbt_mixture_tmp.AutoSize = true;
            this.rbt_mixture_tmp.Location = new System.Drawing.Point(426, 172);
            this.rbt_mixture_tmp.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.rbt_mixture_tmp.Name = "rbt_mixture_tmp";
            this.rbt_mixture_tmp.Size = new System.Drawing.Size(167, 28);
            this.rbt_mixture_tmp.TabIndex = 6;
            this.rbt_mixture_tmp.Text = "高-常温组合";
            this.rbt_mixture_tmp.UseVisualStyleBackColor = true;
            this.rbt_mixture_tmp.CheckedChanged += new System.EventHandler(this.OnTempStateChange);
            // 
            // rbt_hight_tmp
            // 
            this.rbt_hight_tmp.AutoSize = true;
            this.rbt_hight_tmp.Checked = true;
            this.rbt_hight_tmp.Location = new System.Drawing.Point(279, 172);
            this.rbt_hight_tmp.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.rbt_hight_tmp.Name = "rbt_hight_tmp";
            this.rbt_hight_tmp.Size = new System.Drawing.Size(83, 28);
            this.rbt_hight_tmp.TabIndex = 4;
            this.rbt_hight_tmp.TabStop = true;
            this.rbt_hight_tmp.Text = "高温";
            this.rbt_hight_tmp.UseVisualStyleBackColor = true;
            this.rbt_hight_tmp.CheckedChanged += new System.EventHandler(this.OnTempStateChange);
            // 
            // rbt_normal_tmp
            // 
            this.rbt_normal_tmp.AutoSize = true;
            this.rbt_normal_tmp.Location = new System.Drawing.Point(129, 172);
            this.rbt_normal_tmp.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.rbt_normal_tmp.Name = "rbt_normal_tmp";
            this.rbt_normal_tmp.Size = new System.Drawing.Size(83, 28);
            this.rbt_normal_tmp.TabIndex = 4;
            this.rbt_normal_tmp.Text = "常温";
            this.rbt_normal_tmp.UseVisualStyleBackColor = true;
            this.rbt_normal_tmp.CheckedChanged += new System.EventHandler(this.OnTempStateChange);
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label2.Location = new System.Drawing.Point(26, 172);
            this.label2.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(73, 24);
            this.label2.TabIndex = 3;
            this.label2.Text = "环境:";
            // 
            // txt_policy_name
            // 
            this.txt_policy_name.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.txt_policy_name.Location = new System.Drawing.Point(144, 93);
            this.txt_policy_name.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.txt_policy_name.Name = "txt_policy_name";
            this.txt_policy_name.Size = new System.Drawing.Size(802, 35);
            this.txt_policy_name.TabIndex = 2;
            // 
            // label3
            // 
            this.label3.AutoSize = true;
            this.label3.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label3.Location = new System.Drawing.Point(12, 39);
            this.label3.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label3.Name = "label3";
            this.label3.Size = new System.Drawing.Size(123, 24);
            this.label3.TabIndex = 1;
            this.label3.Text = "子文件夹:";
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label1.Location = new System.Drawing.Point(12, 100);
            this.label1.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(98, 24);
            this.label1.TabIndex = 1;
            this.label1.Text = "文件名:";
            // 
            // m_btn_select_dir
            // 
            this.m_btn_select_dir.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_btn_select_dir.Location = new System.Drawing.Point(976, 34);
            this.m_btn_select_dir.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.m_btn_select_dir.Name = "m_btn_select_dir";
            this.m_btn_select_dir.Size = new System.Drawing.Size(138, 40);
            this.m_btn_select_dir.TabIndex = 0;
            this.m_btn_select_dir.Text = "选择";
            this.m_btn_select_dir.UseVisualStyleBackColor = true;
            this.m_btn_select_dir.Click += new System.EventHandler(this.OnBtnSelectDirClick);
            // 
            // btn_save
            // 
            this.btn_save.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.btn_save.Location = new System.Drawing.Point(976, 140);
            this.btn_save.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.btn_save.Name = "btn_save";
            this.btn_save.Size = new System.Drawing.Size(138, 63);
            this.btn_save.TabIndex = 0;
            this.btn_save.Text = "保存方案";
            this.btn_save.UseVisualStyleBackColor = true;
            this.btn_save.Click += new System.EventHandler(this.btn_save_Click);
            // 
            // EditPolicyDlg
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(9F, 18F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(1132, 891);
            this.Controls.Add(this.panel1);
            this.Controls.Add(this.m_pal_policy_list);
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(4, 4, 4, 4);
            this.Name = "EditPolicyDlg";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterParent;
            this.Text = "方案编辑";
            this.panel1.ResumeLayout(false);
            this.panel1.PerformLayout();
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.FlowLayoutPanel m_pal_policy_list;
        private System.Windows.Forms.Panel panel1;
        private System.Windows.Forms.Button btn_save;
        private System.Windows.Forms.TextBox txt_policy_name;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.RadioButton rbt_hight_tmp;
        private System.Windows.Forms.RadioButton rbt_normal_tmp;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.Button m_btn_select_dir;
        private System.Windows.Forms.RadioButton rbt_mixture_tmp;
        private System.Windows.Forms.TextBox txt_sub_path;
    }
}