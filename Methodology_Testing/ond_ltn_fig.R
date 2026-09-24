res<-readRDS("/tmp/ond_ltn.rds")
MON<-c("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
dlab<-function(d){d<-round(d);sprintf("%s-d%d",MON[(d-1)%/%3+1],(d-1)%%3+1)}
E<-res$regime=="early (Aug-Sep)"
OUT<-"Methodology_Testing/figs"; dir.create(OUT,showWarnings=FALSE,recursive=TRUE)
C_E<-"#1B72B8"; C_L<-"#C1471E"; C_W<-"#EDE3D2"; GRID<-"#DDD8CF"; INK<-"#2A2622"; MUT<-"#7A736A"

## FIG 1 - dekadal rainfall normal by regime, window shaded
png(file.path(OUT,"ond_ltn_fig1_chirps_profile.png"),1500,760,res=150)
par(mar=c(5.2,5.4,4.6,1.6),xpd=NA)
dk<-19:36
mE<-sapply(dk,function(d) median(sapply(res$p_prof[E],function(p)p[d-18])))
mL<-sapply(dk,function(d) median(sapply(res$p_prof[!E],function(p)p[d-18])))
plot(NA,xlim=c(19,36),ylim=c(0,max(mE,mL)*1.18),axes=FALSE,xlab="",ylab="")
rect(27.5,0,33.5,max(mE,mL)*1.18,col=C_W,border=NA)
abline(h=pretty(c(0,max(mE,mL))),col=GRID,lwd=1)
lines(dk,mE,col=C_E,lwd=2.6); points(dk,mE,pch=19,col=C_E,cex=.75)
lines(dk,mL,col=C_L,lwd=2.6); points(dk,mL,pch=19,col=C_L,cex=.75)
axis(1,at=seq(19,36,2),labels=dlab(seq(19,36,2)),col=GRID,col.axis=MUT,cex.axis=.82,las=2,tck=-.02,lwd=1)
axis(2,las=1,col=GRID,col.axis=MUT,cex.axis=.86,tck=-.02)
mtext("CHIRPS dekadal rainfall normal, 1996-2025",3,line=2.7,adj=0,cex=1.22,font=2,col=INK)
mtext("Median across counties in each survey-defined OND regime",3,line=1.25,adj=0,cex=.92,col=MUT)
mtext("Dekad",1,line=4.0,cex=.95,col=MUT); mtext("mm per dekad",2,line=3.9,cex=.95,col=MUT)
text(30.5,max(mE,mL)*1.11,"detection window  dk 28-33",col="#9A8E77",cex=.85,font=2)
text(19.2,max(mE,mL)*0.76,"early (Aug-Sep) regime",col=C_E,cex=.92,font=2,adj=0)
text(19.2,max(mE,mL)*0.24,"late (Oct-Nov) regime",col=C_L,cex=.92,font=2,adj=0)
dev.off()

## FIG 2 - Aug-Sep rain separates the regimes (the independent confirmation)
png(file.path(OUT,"ond_ltn_fig2_separation.png"),1500,760,res=150)
par(mfrow=c(1,2),mar=c(5.0,5.6,4.8,1.2),oma=c(0,0,2.4,0),xpd=NA)
bx<-function(x,g,ttl,ylb){
  plot(NA,xlim=c(.5,2.5),ylim=range(x)*c(.9,1.15)+c(-1,1),axes=FALSE,xlab="",ylab="")
  abline(h=pretty(range(x)),col=GRID,lwd=1)
  for(j in 1:2){cl<-if(j==1)C_E else C_L; v<-x[g==j]
    rect(j-.26,quantile(v,.25),j+.26,quantile(v,.75),col=paste0(cl,"33"),border=cl,lwd=1.8)
    segments(j-.26,median(v),j+.26,median(v),col=cl,lwd=3)
    points(jitter(rep(j,length(v)),amount=.10),v,pch=19,col=paste0(cl,"BB"),cex=.85)}
  axis(1,at=1:2,labels=c("early\n(Aug-Sep)","late\n(Oct-Nov)"),col=GRID,col.axis=MUT,cex.axis=.86,tck=-.02,padj=.55)
  axis(2,las=1,col=GRID,col.axis=MUT,cex.axis=.84,tck=-.02)
  mtext(ttl,3,line=1.5,adj=0,cex=1.0,font=2,col=INK); mtext(ylb,2,line=4.0,cex=.88,col=MUT)}
g<-ifelse(E,1,2)
bx(res$r_augsep,g,"Aug-Sep rainfall","mm (CHIRPS normal)")
text(1.5,max(res$r_augsep)*1.10,"Wilcoxon p = 0.009   AUC = 0.79",cex=.86,col=INK,font=2)
bx(res$chirps_onset,g,"CHIRPS climatological onset dekad","dekad (25/20 mm rule)")
text(1.5,max(res$chirps_onset)*1.09,"Wilcoxon p = 0.030",cex=.86,col=INK,font=2)
mtext("CHIRPS climatology independently separates the two survey-derived regimes",3,outer=TRUE,line=.2,adj=.02,cex=1.14,font=2,col=INK)
dev.off()

## FIG 3 - window coverage, all counties vs dry-break counties only
png(file.path(OUT,"ond_ltn_fig3_window.png"),1500,860,res=150)
par(mar=c(5.4,10.6,4.8,7.0),xpd=NA)
D<-res$r_augsep<100
o<-order(D,-res$chirps_onset); n<-nrow(res)
plot(NA,xlim=c(19,35),ylim=c(.4,n+.6),axes=FALSE,xlab="",ylab="")
rect(27.5,.4,33.5,n+.6,col=C_W,border=NA)
abline(v=seq(20,34,2),col=GRID,lwd=1)
for(r in seq_len(n)){i<-o[r]; cl<-if(E[i])C_E else C_L
  segments(res$onset_survey[i],r,res$chirps_onset[i],r,col=paste0(cl,"55"),lwd=1.6)
  points(res$chirps_onset[i],r,pch=19,col=cl,cex=1.15)
  points(res$onset_survey[i],r,pch=1,col=cl,cex=1.05,lwd=1.8)}
axis(2,at=seq_len(n),labels=res$county[o],las=1,col=GRID,col.axis=INK,cex.axis=.72,tck=-.012,lwd=1)
axis(1,at=seq(19,35,2),labels=dlab(seq(19,35,2)),col=GRID,col.axis=MUT,cex.axis=.8,las=2,tck=-.02)
sep<-sum(!D[o[1:n]]==FALSE)  # index where dry-break group starts
brk<-max(which(!D[o]))+.5; segments(19,brk,35,brk,col=MUT,lwd=1.2,lty=3)
text(35.4,mean(c(brk,n+.6)),"dry break\n(distinct OND)\n13/13 inside",adj=0,cex=.76,col=INK,font=2)
text(35.4,mean(c(.4,brk)),"continuous rain\n(no OND onset\nto detect)",adj=0,cex=.76,col=MUT)
mtext("Climatological onset vs farmer-reported onset, against the shipped window",3,line=2.7,adj=0,cex=1.18,font=2,col=INK)
mtext("Filled = CHIRPS 25/20 mm normal   Open = survey median   Shaded = detection window dk 28-33",3,line=1.25,adj=0,cex=.85,col=MUT)
mtext("Dekad",1,line=4.1,cex=.92,col=MUT)
dev.off()
cat("figures written\n"); cat(list.files(OUT,pattern="ond_ltn"),sep="\n")
