// iOS side of the platform layer (unity/Assets/DoodLive/Scripts/Platform/IosPlatform.cs). Plain UIKit, no third-party
// code. Called from C# through [DllImport("__Internal")]. Not yet run on a device (2026-11-22).
#import <UIKit/UIKit.h>
#import <AVFoundation/AVFoundation.h>

extern UIViewController *UnityGetGLViewController(void);

static NSString *DLString(const char *s) { return s ? [NSString stringWithUTF8String:s] : @""; }

// The view controller to present on, and an anchor for iPad popovers (centre of the screen).
static void DLPresent(UIViewController *vc)
{
    UIViewController *root = UnityGetGLViewController();
    if (vc.popoverPresentationController) {
        vc.popoverPresentationController.sourceView = root.view;
        vc.popoverPresentationController.sourceRect = CGRectMake(CGRectGetMidX(root.view.bounds), CGRectGetMidY(root.view.bounds), 1, 1);
        vc.popoverPresentationController.permittedArrowDirections = 0;
    }
    [root presentViewController:vc animated:YES completion:nil];
}

extern "C" {

void DLHaptic(int strength)
{
    UIImpactFeedbackGenerator *g = [[UIImpactFeedbackGenerator alloc] initWithStyle:strength > 0 ? UIImpactFeedbackStyleMedium : UIImpactFeedbackStyleLight];
    [g prepare];
    [g impactOccurred];
}

void DLShareFile(const char *path, const char *title)
{
    NSURL *url = [NSURL fileURLWithPath:DLString(path)];
    UIActivityViewController *vc = [[UIActivityViewController alloc] initWithActivityItems:@[url] applicationActivities:nil];
    vc.title = DLString(title);
    DLPresent(vc);
}

void DLPrintFile(const char *path, const char *title)
{
    NSURL *url = [NSURL fileURLWithPath:DLString(path)];
    UIPrintInteractionController *pc = [UIPrintInteractionController sharedPrintController];
    UIPrintInfo *info = [UIPrintInfo printInfo];
    info.outputType = UIPrintInfoOutputGeneral;
    info.jobName = DLString(title);
    pc.printInfo = info;
    pc.printingItem = url;   // the PDF prints unchanged: the corner markers must stay square for scanning
    UIViewController *root = UnityGetGLViewController();
    if (UIDevice.currentDevice.userInterfaceIdiom == UIUserInterfaceIdiomPad)
        [pc presentFromRect:CGRectMake(CGRectGetMidX(root.view.bounds), CGRectGetMidY(root.view.bounds), 1, 1) inView:root.view animated:YES completionHandler:nil];
    else
        [pc presentAnimated:YES completionHandler:nil];
}

void DLAudioPlayback(void)
{
    // a story app must be heard with the ring / silent switch on silent; the in-app mute stays the child's control
    NSError *err = nil;
    [[AVAudioSession sharedInstance] setCategory:AVAudioSessionCategoryPlayback mode:AVAudioSessionModeDefault options:0 error:&err];
    [[AVAudioSession sharedInstance] setActive:YES error:&err];
}

void DLOpenSettings(void)
{
    NSURL *url = [NSURL URLWithString:UIApplicationOpenSettingsURLString];
    [[UIApplication sharedApplication] openURL:url options:@{} completionHandler:nil];
}

}
