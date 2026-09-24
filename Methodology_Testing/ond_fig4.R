m<-readRDS("/tmp/ond_pheno.rds")
MON<-c("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
dlab<-function(d){d<-round(d);sprintf("%s-d%d",MON[(d-1)%/%3+1],(d-1)%%3+1)}
OUT<-"Methodology_Testing/figs"
C_E<-"#1B72B8"; C_L<-"#C1471E"; C_W<-"#EDE3D2"; GRID<-"#DDD8CF"; INK<-"#2A2622"; MUT<-"#7A736A"; C_M<-"#4E7A3A"
E<-m$regime=="early (Aug-Sep)"; D<-m$r_augsep<100

## FIG 4 - MODIS green-up vs CHIRPS onset, coloured by regime
png(file.path(OUT,"ond_ltn_fig4_modis.png"),1560,780,res=150)
par(mfrow=c(1,2),mar=c(5.4,6.4,5.4,1.6),oma=c(0,0,3.0,0),xpd=FALSE)
# panel A scatter  (xpd=FALSE so the 1:1 line and shading stay inside the panel)
XL<-c(18,32); YL<-c(22.6,33.4)
plot(NA,xlim=XL,ylim=YL,axes=FALSE,xlab="",ylab="")
rect(27.5,YL[1],33.5,YL[2],col=C_W,border=NA)          # window on the CHIRPS axis
rect(XL[1],27.5,XL[2],33.5,col=paste0(C_W,"66"),border=NA)   # window on the MODIS axis
abline(h=seq(24,32,2),v=seq(18,32,2),col=GRID,lwd=1)
segments(XL[1],XL[1],XL[2],XL[2],col=MUT,lty=3,lwd=1.3)
points(m$chirps_onset,m$g2,pch=19,col=ifelse(E,C_E,C_L),cex=1.25)
axis(1,at=seq(18,32,2),labels=dlab(seq(18,32,2)),col=GRID,col.axis=MUT,cex.axis=.76,las=2,tck=-.02)
axis(2,at=seq(24,32,2),labels=dlab(seq(24,32,2)),las=1,col=GRID,col.axis=MUT,cex.axis=.76,tck=-.02)
mtext("A. Two independent climatologies agree",3,line=1.7,adj=0,cex=1.0,font=2,col=INK)
mtext("CHIRPS onset (25/20 mm normal)",1,line=4.5,cex=.86,col=MUT)
mtext("MODIS 2nd-cycle green-up",2,line=5.0,cex=.86,col=MUT)
text(18.3,33.1,expression(paste("Spearman ",rho," = +0.73,  p < 0.001")),adj=0,cex=.82,font=2,col=INK)
text(26.9,23.1,"dotted 1:1",adj=1,cex=.74,col=MUT)
legend("bottomright",c("early regime","late regime"),pch=19,col=c(C_E,C_L),bty="n",cex=.78,pt.cex=1.1,text.col=INK,inset=c(.02,.10))
# panel B second-cycle detection rate
par(xpd=FALSE)
plot(NA,xlim=c(.5,2.5),ylim=c(0,.80),axes=FALSE,xlab="",ylab="")
abline(h=seq(0,.7,.1),col=GRID,lwd=1)
for(j in 1:2){cl<-if(j==1)C_E else C_L; v<-m$frac2[if(j==1)E else !E]
 rect(j-.26,quantile(v,.25),j+.26,quantile(v,.75),col=paste0(cl,"33"),border=cl,lwd=1.8)
 segments(j-.26,median(v),j+.26,median(v),col=cl,lwd=3)
 points(jitter(rep(j,length(v)),amount=.10),v,pch=19,col=paste0(cl,"BB"),cex=.9)}
axis(1,at=1:2,labels=c("early\n(Aug-Sep)","late\n(Oct-Nov)"),col=GRID,col.axis=MUT,cex.axis=.84,tck=-.02,padj=.55)
axis(2,at=seq(0,.7,.1),labels=paste0(seq(0,70,10),"%"),las=1,col=GRID,col.axis=MUT,cex.axis=.8,tck=-.02)
mtext("B. How often a 2nd season exists at all",3,line=1.6,adj=0,cex=1.0,font=2,col=INK)
mtext("years with a detected 2nd green-up cycle",2,line=4.4,cex=.86,col=MUT)
text(1.5,.78,"Wilcoxon p = 0.029",cex=.84,font=2,col=INK)
mtext("MODIS MCD12Q2 cropland green-up, 2001-2023, as a third independent anchor",3,outer=TRUE,line=.4,adj=.02,cex=1.14,font=2,col=INK)
dev.off()

## FIG 5 - three-anchor triangulation for the dry-break counties
png(file.path(OUT,"ond_ltn_fig5_triangulate.png"),1500,760,res=150)
par(mar=c(5.4,10.2,5.0,9.4),xpd=NA)
s<-m[D,]; s<-s[order(-s$chirps_onset),]; n<-nrow(s)
plot(NA,xlim=c(22.4,34),ylim=c(.4,n+.6),axes=FALSE,xlab="",ylab="")
rect(27.5,.4,33.5,n+.6,col=C_W,border=NA); abline(v=seq(23,34,1),col=GRID,lwd=1)
for(r in 1:n){y<-r
 segments(min(s$onset_survey[r],s$chirps_onset[r],s$g2[r]),y,max(s$onset_survey[r],s$chirps_onset[r],s$g2[r]),y,col=GRID,lwd=2.4)
 points(s$onset_survey[r],y,pch=1,col=INK,cex=1.15,lwd=1.9)
 points(s$chirps_onset[r],y,pch=19,col=C_E,cex=1.15)
 points(s$g2[r],y,pch=17,col=C_M,cex=1.05)}
axis(2,at=1:n,labels=s$county,las=1,col=GRID,col.axis=INK,cex.axis=.78,tck=-.014)
axis(1,at=seq(23,34,1),labels=dlab(seq(23,34,1)),col=GRID,col.axis=MUT,cex.axis=.78,las=2,tck=-.02)
legend(34.4,n*0.88,c("farmer survey","CHIRPS normal","MODIS green-up"),pch=c(1,19,17),
  col=c(INK,C_E,C_M),bty="n",cex=.82,pt.cex=1.1,text.col=INK,y.intersp=1.5)
mtext("Three independent anchors, counties with a genuine dry break",3,line=2.9,adj=0,cex=1.18,font=2,col=INK)
mtext("All 13 fall inside the shipped window dk 28-33 on both climatological anchors",3,line=1.4,adj=0,cex=.88,col=MUT)
mtext("Dekad",1,line=4.2,cex=.9,col=MUT)
dev.off(); cat("ok\n")
