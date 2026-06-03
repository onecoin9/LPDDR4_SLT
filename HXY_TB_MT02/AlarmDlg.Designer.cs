namespace Hsg.View
{
    partial class AlarmDlg
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(AlarmDlg));
            this.m_btn_retry = new System.Windows.Forms.Button();
            this.m_btn_cancel = new System.Windows.Forms.Button();
            this.m_lab_alarm = new System.Windows.Forms.Label();
            this.SuspendLayout();
            // 
            // m_btn_retry
            // 
            this.m_btn_retry.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(0)))), ((int)(((byte)(192)))), ((int)(((byte)(0)))));
            this.m_btn_retry.ForeColor = System.Drawing.SystemColors.ControlText;
            this.m_btn_retry.Location = new System.Drawing.Point(35, 101);
            this.m_btn_retry.Name = "m_btn_retry";
            this.m_btn_retry.Size = new System.Drawing.Size(102, 44);
            this.m_btn_retry.TabIndex = 0;
            this.m_btn_retry.Text = "重测";
            this.m_btn_retry.UseVisualStyleBackColor = false;
            this.m_btn_retry.Click += new System.EventHandler(this.m_btn_retry_Click);
            // 
            // m_btn_cancel
            // 
            this.m_btn_cancel.BackColor = System.Drawing.SystemColors.MenuHighlight;
            this.m_btn_cancel.Location = new System.Drawing.Point(177, 101);
            this.m_btn_cancel.Name = "m_btn_cancel";
            this.m_btn_cancel.Size = new System.Drawing.Size(102, 44);
            this.m_btn_cancel.TabIndex = 0;
            this.m_btn_cancel.Text = "返回";
            this.m_btn_cancel.UseVisualStyleBackColor = false;
            this.m_btn_cancel.Click += new System.EventHandler(this.m_btn_cancel_Click);
            // 
            // m_lab_alarm
            // 
            this.m_lab_alarm.Location = new System.Drawing.Point(35, 18);
            this.m_lab_alarm.Name = "m_lab_alarm";
            this.m_lab_alarm.Size = new System.Drawing.Size(256, 77);
            this.m_lab_alarm.TabIndex = 1;
            this.m_lab_alarm.Text = "label11111111111111111111111111111111";
            // 
            // AlarmDlg
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(14F, 29F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.BackColor = System.Drawing.SystemColors.ButtonHighlight;
            this.ClientSize = new System.Drawing.Size(324, 161);
            this.ControlBox = false;
            this.Controls.Add(this.m_lab_alarm);
            this.Controls.Add(this.m_btn_cancel);
            this.Controls.Add(this.m_btn_retry);
            this.Font = new System.Drawing.Font("Microsoft Sans Serif", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(5);
            this.Name = "AlarmDlg";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.Text = "警告处理";
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.Button m_btn_retry;
        private System.Windows.Forms.Button m_btn_cancel;
        private System.Windows.Forms.Label m_lab_alarm;
    }
}