namespace Hsg.View
{
    partial class Password
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(Password));
            this.m_btn_ok = new System.Windows.Forms.Button();
            this.m_btn_cancel = new System.Windows.Forms.Button();
            this.m_txt_password = new System.Windows.Forms.TextBox();
            this.label1 = new System.Windows.Forms.Label();
            this.SuspendLayout();
            // 
            // m_btn_ok
            // 
            this.m_btn_ok.Location = new System.Drawing.Point(23, 125);
            this.m_btn_ok.Margin = new System.Windows.Forms.Padding(4);
            this.m_btn_ok.Name = "m_btn_ok";
            this.m_btn_ok.Size = new System.Drawing.Size(101, 47);
            this.m_btn_ok.TabIndex = 1;
            this.m_btn_ok.Text = "确定";
            this.m_btn_ok.UseVisualStyleBackColor = true;
            this.m_btn_ok.Click += new System.EventHandler(this.OnOkBtnClick);
            // 
            // m_btn_cancel
            // 
            this.m_btn_cancel.Location = new System.Drawing.Point(179, 125);
            this.m_btn_cancel.Margin = new System.Windows.Forms.Padding(4);
            this.m_btn_cancel.Name = "m_btn_cancel";
            this.m_btn_cancel.Size = new System.Drawing.Size(112, 47);
            this.m_btn_cancel.TabIndex = 3;
            this.m_btn_cancel.Text = "取消";
            this.m_btn_cancel.UseVisualStyleBackColor = true;
            this.m_btn_cancel.Click += new System.EventHandler(this.OnCancelBtnClick);
            // 
            // m_txt_password
            // 
            this.m_txt_password.Location = new System.Drawing.Point(83, 61);
            this.m_txt_password.Margin = new System.Windows.Forms.Padding(4);
            this.m_txt_password.Name = "m_txt_password";
            this.m_txt_password.PasswordChar = '*';
            this.m_txt_password.Size = new System.Drawing.Size(207, 35);
            this.m_txt_password.TabIndex = 0;
            this.m_txt_password.KeyDown += new System.Windows.Forms.KeyEventHandler(this.OnPwdInputKeyDown);
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Location = new System.Drawing.Point(21, 68);
            this.label1.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(82, 24);
            this.label1.TabIndex = 2;
            this.label1.Text = "密码：";
            // 
            // Password
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(12F, 24F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(317, 187);
            this.Controls.Add(this.label1);
            this.Controls.Add(this.m_txt_password);
            this.Controls.Add(this.m_btn_cancel);
            this.Controls.Add(this.m_btn_ok);
            this.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(4);
            this.Name = "Password";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.Text = "执行权限确认";
            this.Load += new System.EventHandler(this.Password_Load);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Button m_btn_ok;
        private System.Windows.Forms.Button m_btn_cancel;
        private System.Windows.Forms.TextBox m_txt_password;
        private System.Windows.Forms.Label label1;
    }
}