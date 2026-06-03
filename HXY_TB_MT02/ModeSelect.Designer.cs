namespace Hsg.View
{
    partial class ModeSelect
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(ModeSelect));
            this.label1 = new System.Windows.Forms.Label();
            this.btn_policy_manager = new Hsg.View.FocusColorButton();
            this.m_btn_debug_mode = new Hsg.View.FocusColorButton();
            this.m_btn_offline_mode = new Hsg.View.FocusColorButton();
            this.SuspendLayout();
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.BackColor = System.Drawing.Color.Transparent;
            this.label1.Font = new System.Drawing.Font("Microsoft Sans Serif", 36F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.label1.ForeColor = System.Drawing.Color.Yellow;
            this.label1.Location = new System.Drawing.Point(82, 103);
            this.label1.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(473, 82);
            this.label1.TabIndex = 1;
            this.label1.Text = "测试控制系统";
            // 
            // btn_policy_manager
            // 
            this.btn_policy_manager.BackColor = System.Drawing.Color.Thistle;
            this.btn_policy_manager.BackgroundImageLayout = System.Windows.Forms.ImageLayout.None;
            this.btn_policy_manager.Font = new System.Drawing.Font("新宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.btn_policy_manager.ForeColor = System.Drawing.Color.Black;
            this.btn_policy_manager.ImageKey = "(无)";
            this.btn_policy_manager.Location = new System.Drawing.Point(71, 451);
            this.btn_policy_manager.Margin = new System.Windows.Forms.Padding(4, 5, 4, 5);
            this.btn_policy_manager.Name = "btn_policy_manager";
            this.btn_policy_manager.Size = new System.Drawing.Size(127, 90);
            this.btn_policy_manager.TabIndex = 3;
            this.btn_policy_manager.TabStop = false;
            this.btn_policy_manager.Tag = "2";
            this.btn_policy_manager.Text = "方案管理";
            this.btn_policy_manager.UseMnemonic = false;
            this.btn_policy_manager.UseVisualStyleBackColor = false;
            this.btn_policy_manager.Click += new System.EventHandler(this.On_Policy_Manager_Click);
            // 
            // m_btn_debug_mode
            // 
            this.m_btn_debug_mode.BackColor = System.Drawing.Color.DeepSkyBlue;
            this.m_btn_debug_mode.BackgroundImageLayout = System.Windows.Forms.ImageLayout.None;
            this.m_btn_debug_mode.Font = new System.Drawing.Font("新宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_btn_debug_mode.ForeColor = System.Drawing.Color.Black;
            this.m_btn_debug_mode.ImageKey = "(无)";
            this.m_btn_debug_mode.Location = new System.Drawing.Point(418, 451);
            this.m_btn_debug_mode.Margin = new System.Windows.Forms.Padding(4, 5, 4, 5);
            this.m_btn_debug_mode.Name = "m_btn_debug_mode";
            this.m_btn_debug_mode.Size = new System.Drawing.Size(127, 90);
            this.m_btn_debug_mode.TabIndex = 2;
            this.m_btn_debug_mode.TabStop = false;
            this.m_btn_debug_mode.Tag = "2";
            this.m_btn_debug_mode.Text = "调试模式";
            this.m_btn_debug_mode.UseMnemonic = false;
            this.m_btn_debug_mode.UseVisualStyleBackColor = false;
            this.m_btn_debug_mode.Click += new System.EventHandler(this.m_btn_debug_mode_Click);
            // 
            // m_btn_offline_mode
            // 
            this.m_btn_offline_mode.BackColor = System.Drawing.Color.Aqua;
            this.m_btn_offline_mode.Font = new System.Drawing.Font("新宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.m_btn_offline_mode.ForeColor = System.Drawing.SystemColors.ControlDarkDark;
            this.m_btn_offline_mode.Location = new System.Drawing.Point(244, 451);
            this.m_btn_offline_mode.Margin = new System.Windows.Forms.Padding(4, 5, 4, 5);
            this.m_btn_offline_mode.Name = "m_btn_offline_mode";
            this.m_btn_offline_mode.Size = new System.Drawing.Size(127, 90);
            this.m_btn_offline_mode.TabIndex = 1;
            this.m_btn_offline_mode.TabStop = false;
            this.m_btn_offline_mode.Tag = "1";
            this.m_btn_offline_mode.Text = "本地模式";
            this.m_btn_offline_mode.UseMnemonic = false;
            this.m_btn_offline_mode.UseVisualStyleBackColor = false;
            this.m_btn_offline_mode.Click += new System.EventHandler(this.m_btn_offline_mode_Click);
            // 
            // ModeSelect
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(9F, 18F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.AutoValidate = System.Windows.Forms.AutoValidate.Disable;
            this.BackColor = System.Drawing.SystemColors.ControlDark;
            this.BackgroundImage = ((System.Drawing.Image)(resources.GetObject("$this.BackgroundImage")));
            this.BackgroundImageLayout = System.Windows.Forms.ImageLayout.Stretch;
            this.ClientSize = new System.Drawing.Size(673, 571);
            this.Controls.Add(this.btn_policy_manager);
            this.Controls.Add(this.label1);
            this.Controls.Add(this.m_btn_debug_mode);
            this.Controls.Add(this.m_btn_offline_mode);
            this.DoubleBuffered = true;
            this.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedDialog;
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(4, 5, 4, 5);
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "ModeSelect";
            this.SizeGripStyle = System.Windows.Forms.SizeGripStyle.Hide;
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private FocusColorButton m_btn_offline_mode;
        private FocusColorButton m_btn_debug_mode;
        private System.Windows.Forms.Label label1;
        private FocusColorButton btn_policy_manager;
    }
}