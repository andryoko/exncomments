/**
 * Created by okoneshnikov on 17.09.16.
 */

function onDelete(comment_id, viewer_id) {
  $.ajax({
    type: "POST",
    url: "/comment/delete/",
    data: {
      comment_id: comment_id,
      viewer_id: viewer_id
    }
  }).done(function(result) {
    window.location.reload()
  }).error(function(data) {
    var result = data.responseJSON

    if (result.message) {
      alert(result.message);
    }
  });
}