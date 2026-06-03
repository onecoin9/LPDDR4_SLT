namespace Hsg.View
{
    partial class ChoiseDlg
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(ChoiseDlg));
            this.m_txt_content = new System.Windows.Forms.Label();
            this.m_btn_ok = new System.Windows.Forms.Button();
            this.button2 = new System.Windows.Forms.Button();
            this.SuspendLayout();
            // 
            // m_txt_content
            // 
            this.m_txt_content.Anchor = ((System.Windows.Forms.AnchorStyles)(((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.m_txt_content.AutoSize = true;
            this.m_txt_content.Location = new System.Drawing.Point(20, 18);
            this.m_txt_content.Name = "m_txt_content";
            this.m_txt_content.Size = new System.Drawing.Size(88, 24);
            this.m_txt_content.TabIndex = 0;
            this.m_txt_content.Text = "label1";
            // 
            // m_btn_ok
            // 
            this.m_btn_ok.Location = new System.Drawing.Point(23, 59);
            this.m_btn_ok.Name = "m_btn_ok";
            this.m_btn_ok.Size = new System.Drawing.Size(75, 23);
            this.m_btn_ok.TabIndex = 1;
            this.m_btn_ok.Text = "确定";
            this.m_btn_ok.UseVisualStyleBackColor = true;
            this.m_btn_ok.Click += new System.EventHandler(this.OnOkClick);
            // 
            // button2
            // 
            this.button2.Location = new System.Drawing.Point(143, 59);
            this.button2.Name = "button2";
            this.button2.Size = new System.Drawing.Size(75, 23);
            this.button2.TabIndex = 1;
            this.button2.Text = "取消";
            this.button2.UseVisualStyleBackColor = true;
            this.button2.Click += new System.EventHandler(this.OnClickCancel);
            // 
            // ChoiseDlg
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(13F, 24F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.BackgroundImageLayout = System.Windows.Forms.ImageLayout.Center;
            this.ClientSize = new System.Drawing.Size(263, 94);
            this.Controls.Add(this.button2);
            this.Controls.Add(this.m_btn_ok);
            this.Controls.Add(this.m_txt_content);
            this.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(4);
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "ChoiseDlg";
            this.ShowIcon = false;
            this.ShowInTaskbar = false;
            this.SizeGripStyle = System.Windows.Forms.SizeGripStyle.Hide;
            this.StartPosition = System.Windows.Forms.FormStartPosition.Manual;
            this.Text = "ChoiseDlg";
            this.Load += new System.EventHandler(this.ChoiseDlg_Load);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Label m_txt_content;
        private System.Windows.Forms.Button m_btn_ok;
        private System.Windows.Forms.Button button2;
    }
}