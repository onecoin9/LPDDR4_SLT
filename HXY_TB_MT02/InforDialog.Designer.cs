namespace Hsg.View
{
    partial class InforDialog
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(InforDialog));
            this.m_rbx_content = new System.Windows.Forms.RichTextBox();
            this.SuspendLayout();
            // 
            // m_rbx_content
            // 
            this.m_rbx_content.AccessibleRole = System.Windows.Forms.AccessibleRole.Dialog;
            this.m_rbx_content.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.m_rbx_content.Enabled = false;
            this.m_rbx_content.Location = new System.Drawing.Point(1, 1);
            this.m_rbx_content.Margin = new System.Windows.Forms.Padding(4);
            this.m_rbx_content.Name = "m_rbx_content";
            this.m_rbx_content.Size = new System.Drawing.Size(437, 66);
            this.m_rbx_content.TabIndex = 2;
            this.m_rbx_content.Text = "";
            this.m_rbx_content.Click += new System.EventHandler(this.OnFrameClick);
            // 
            // InforDialog
            // 
            this.AccessibleRole = System.Windows.Forms.AccessibleRole.Dialog;
            this.AutoScaleDimensions = new System.Drawing.SizeF(13F, 24F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.AutoValidate = System.Windows.Forms.AutoValidate.Disable;
            this.ClientSize = new System.Drawing.Size(441, 72);
            this.Controls.Add(this.m_rbx_content);
            this.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(4);
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "InforDialog";
            this.ShowIcon = false;
            this.ShowInTaskbar = false;
            this.StartPosition = System.Windows.Forms.FormStartPosition.Manual;
            this.Text = "InforDialog";
            this.TopMost = true;
            this.Deactivate += new System.EventHandler(this.InforDialog_Deactivate);
            this.Load += new System.EventHandler(this.InforDialog_Load);
            this.Click += new System.EventHandler(this.OnFrameClick);
            this.ResumeLayout(false);

        }

        #endregion

        private System.Windows.Forms.RichTextBox m_rbx_content;
    }
}